"""HTTP and real-browser regression checks for both deployable websites.

Run: PHP_BINARY=/path/to/php python3 -m unittest discover -s tests -v
Requires Playwright and Chromium; no production email is sent.
"""
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def available_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


def request(base, path, payload=None, headers=None):
    req = Request(base + path, data=payload, headers=headers or {})
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src', 'action') and value:
                self.links.append(value)


class WebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = tempfile.TemporaryDirectory(prefix='jengara-website-tests-')
        cls.addClassCleanup(cls.runtime.cleanup)
        cls.runtime_dir = Path(cls.runtime.name)
        cls.rate = cls.runtime_dir / 'rate'
        cls.mail = cls.runtime_dir / 'mail'
        cls.mail.mkdir()
        capture = cls.runtime_dir / 'capture.py'
        capture.write_text('import os,sys,tempfile\n'
                           'fd,path=tempfile.mkstemp(suffix=".eml",dir=os.environ["TEST_MAIL_DIR"])\n'
                           'with os.fdopen(fd,"wb") as output: output.write(sys.stdin.buffer.read())\n')
        php = os.environ.get('PHP_BINARY') or shutil.which('php')
        if not php:
            raise RuntimeError('PHP 8.1+ is required. Set PHP_BINARY or add PHP to PATH.')
        php_port, static_port = available_port(), available_port()
        cls.jengara = f'http://127.0.0.1:{php_port}'
        cls.ribyos = f'http://127.0.0.1:{static_port}'
        env = {**os.environ, 'JENGARA_MAIL_RATE_DIR': str(cls.rate), 'TEST_MAIL_DIR': str(cls.mail),
               'JENGARA_MAIL_CONFIG': str(cls.runtime_dir / 'no-config.php')}
        commands = [
            [php, '-d', f'sendmail_path={shlex.quote(sys.executable)} {shlex.quote(str(capture))}',
             '-S', f'127.0.0.1:{php_port}', '-t', str(ROOT)],
            [sys.executable, '-m', 'http.server', str(static_port), '--bind', '127.0.0.1',
             '--directory', str(ROOT / 'ribyos-site')],
        ]
        cls.logs = []
        cls.servers = []
        for index, command in enumerate(commands):
            log = (cls.runtime_dir / f'server-{index}.log').open('w+')
            cls.addClassCleanup(log.close)
            cls.logs.append(log)
            server = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            cls.servers.append(server)
            cls.addClassCleanup(cls.stop_server, server)
        for base, server in zip([cls.jengara, cls.ribyos], cls.servers):
            for attempt in range(100):
                if server.poll() is not None:
                    raise RuntimeError('Test server failed to start')
                try:
                    if request(base, '/')[0] == 200:
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise RuntimeError('Test server did not become ready')
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        executable = os.environ.get('TEST_CHROMIUM') or shutil.which('chromium')
        options = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            options['executable_path'] = executable
        cls.browser = cls.playwright.chromium.launch(**options)
        cls.addClassCleanup(cls.browser.close)

    @staticmethod
    def stop_server(server):
        server.terminate()
        server.wait(timeout=10)

    def setUp(self):
        for path in self.rate.glob('*.json'):
            path.unlink()
        for path in self.mail.glob('*.eml'):
            path.unlink()
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def tearDown(self):
        self.assertEqual(self.errors, [], 'Unexpected browser JavaScript errors')

    def test_all_pages_assets_and_downloads(self):
        count = 0
        for file in sorted(ROOT.rglob('*.html')):
            if '.venv' in file.parts:
                continue
            standalone = (ROOT / 'ribyos-site') in file.parents
            document_root = ROOT / 'ribyos-site' if standalone else ROOT
            base = self.ribyos if standalone else self.jengara
            path = '/' + file.relative_to(document_root).as_posix()
            status, _, body = request(base, path)
            self.assertEqual(status, 200, path)
            self.assertEqual(body, file.read_bytes(), path)
            parser = Links()
            parser.feed(body.decode())
            for link in parser.links:
                parsed = urlsplit(urljoin(base + path, link))
                if parsed.netloc != urlsplit(base).netloc or parsed.path.endswith('.php'):
                    continue
                status, _, body = request(base, parsed.path or '/')
                self.assertEqual(status, 200, (path, link))
                local = document_root / parsed.path.lstrip('/')
                if local.is_dir():
                    local = local / 'index.html'
                self.assertTrue(local.is_file(), (path, link))
                self.assertEqual(body, local.read_bytes(), (path, link))
            count += 1
        self.assertGreaterEqual(count, 26)
        for file in (ROOT / 'downloads').glob('*.pdf'):
            status, headers, body = request(self.jengara, '/downloads/' + file.name)
            self.assertEqual(status, 200)
            self.assertTrue(body.startswith(b'%PDF-'))
            self.assertIn('application/pdf', headers['Content-Type'])

    def test_responsive_layouts(self):
        targets = [(self.jengara, path) for path in ['/', '/labs/', '/ribyos/', '/contact/', '/advisory/', '/insights/', '/resources/']]
        targets.append((self.ribyos, '/'))
        for width in [320, 390, 768, 1024, 1440]:
            self.page.set_viewport_size({'width': width, 'height': 900})
            for base, path in targets:
                with self.subTest(width=width, page=base+path):
                    self.page.goto(base + path)
                    self.page.evaluate('document.fonts.ready')
                    self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width + 1)
                    expect(self.page.locator('h1')).to_be_visible()
                    expect(self.page.locator('main')).to_be_visible()

    def test_mobile_menus_and_keyboard_focus(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        for base, menu_selector, nav_selector in [(self.jengara, '.menu', '#navigation'), (self.ribyos, '.r-menu', '#r-navigation')]:
            self.page.goto(base + '/')
            menu = self.page.locator(menu_selector)
            expect(self.page.locator(nav_selector)).to_be_hidden()
            menu.click()
            expect(menu).to_have_attribute('aria-expanded', 'true')
            expect(self.page.locator(nav_selector)).to_be_visible()
            self.page.keyboard.press('Escape')
            expect(menu).to_have_attribute('aria-expanded', 'false')
            expect(menu).to_be_focused()
            menu.click()
            self.page.locator(nav_selector + ' a').first.click()
            expect(menu).to_have_attribute('aria-expanded', 'false')

    def test_product_tabs_and_concept_walkthrough(self):
        self.page.goto(self.ribyos)
        tabs = self.page.get_by_role('tab')
        tabs.first.focus()
        self.page.keyboard.press('ArrowRight')
        expect(self.page.get_by_role('tab', name='Enterprise', exact=True)).to_have_attribute('aria-selected', 'true')
        expect(self.page.locator('#panel-enterprise')).to_be_visible()
        expect(self.page.locator('#panel-studio')).to_be_hidden()
        self.page.keyboard.press('End')
        expect(self.page.get_by_role('tab', name='Marketplace', exact=True)).to_be_focused()
        expect(self.page.locator('#panel-marketplace')).to_be_visible()
        self.page.keyboard.press('Home')
        self.page.locator('#walkthrough').click()
        expect(self.page.locator('#concept-status')).to_have_text('Concept complete · Draft awaits human review.')
        expect(self.page.locator('#walkthrough')).to_be_enabled()
        self.assertEqual(self.page.locator('[data-step].is-active').count(), 4)
        self.page.emulate_media(reduced_motion='no-preference')
        self.page.locator('#walkthrough').click()
        expect(self.page.locator('#walkthrough')).to_be_disabled()
        expect(self.page.locator('#concept-status')).to_have_text('Concept complete · Draft awaits human review.', timeout=6000)
        expect(self.page.locator('#walkthrough')).to_be_enabled()
        self.page.locator('#walkthrough').click()
        tabs.nth(1).click()
        expect(self.page.locator('#walkthrough')).to_be_enabled()
        expect(self.page.locator('#concept-status')).to_have_text('A workflow concept. No live execution.')

    def test_filters_workflow_details_and_dialog_focus(self):
        self.page.goto(self.ribyos + '/#workflows')
        self.assertEqual(self.page.locator('.r-pack:visible').count(), 6)
        self.page.locator('[data-filter=business]').click()
        self.assertEqual(self.page.locator('.r-pack:visible').count(), 3)
        self.assertEqual(self.page.locator('.r-pack[data-category=industry]:visible').count(), 0)
        expect(self.page.locator('#pack-count')).to_have_text('3 planned packs')
        self.page.locator('[data-filter=industry]').click()
        self.assertEqual(self.page.locator('.r-pack[data-category=industry]:visible').count(), 3)
        self.page.locator('[data-filter=all]').click()
        for button in self.page.locator('.r-pack [data-workflow]').all():
            button.click()
            expect(self.page.get_by_role('dialog')).to_be_visible()
            self.assertEqual(self.page.locator('.r-dialog-section').count(), 7)
            expect(self.page.get_by_role('heading', name='Human approval boundary', exact=True)).to_be_visible()
            expect(self.page.get_by_role('heading', name='Proposed success criterion', exact=True)).to_be_visible()
            self.page.keyboard.press('Escape')
            expect(self.page.get_by_role('dialog')).to_be_hidden()
            expect(button).to_be_focused()
        self.page.locator('.r-pack [data-workflow]').first.click()
        self.page.locator('.r-dialog-done').click()
        expect(self.page.get_by_role('dialog')).to_be_hidden()

    def test_concept_surface_links_and_faq(self):
        self.page.goto(self.ribyos)
        for surface in ['studio', 'enterprise', 'marketplace']:
            self.page.locator(f'[data-open-surface={surface}]').click()
            expect(self.page.locator(f'#tab-{surface}')).to_have_attribute('aria-selected', 'true')
            expect(self.page.locator(f'#panel-{surface}')).to_be_visible()
        self.page.locator('#panel-marketplace [data-workflow=procurement]').click()
        expect(self.page.locator('#workflow-title')).to_have_text('A clearer view of suppliers.')
        self.page.locator('.r-dialog-close').click()
        faq = self.page.locator('details').first
        faq.locator('summary').click()
        expect(faq).to_have_attribute('open', '')
        expect(faq.locator('p')).to_contain_text('not an implemented production platform')

    def test_reduced_motion_and_self_hosted_assets(self):
        for base in [self.jengara, self.ribyos]:
            requests = []
            self.page.on('request', lambda req: requests.append(req.url))
            self.page.goto(base)
            self.page.wait_for_load_state('networkidle')
            self.assertTrue(all(urlsplit(url).hostname == '127.0.0.1' for url in requests), requests)
            animations = self.page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length")
            self.assertEqual(animations, 0)
            for item in self.page.locator('[data-reveal]').all():
                self.assertEqual(item.evaluate("element => getComputedStyle(element).opacity"), '1')

    def test_domain_metadata_and_cross_site_links(self):
        self.page.goto(self.ribyos)
        expect(self.page.locator('link[rel=canonical]')).to_have_attribute('href', 'https://ribyos.ai/')
        expect(self.page.locator('.r-header-cta')).to_have_attribute('href', 'https://jengara.ai/contact/?interest=Labs%20collaboration&product=Ribyos')
        for path in ['/', '/labs/', '/ribyos/']:
            self.page.goto(self.jengara + path)
            expect(self.page.locator('a[href="/ribyos/"]').first).to_be_visible()
        self.page.goto(self.jengara + '/ribyos/')
        self.assertGreater(self.page.locator('a[href^="https://ribyos.ai/"]').count(), 0)

    def test_contact_submission_and_ribyos_prefill(self):
        self.page.goto(self.jengara + '/contact/?interest=Labs%20collaboration&product=Ribyos')
        expect(self.page.locator('[name=interest]')).to_have_value('Labs collaboration')
        expect(self.page.locator('form h2')).to_have_text('Let’s talk about Ribyos.')
        expect(self.page.locator('fieldset')).to_be_enabled()
        self.page.locator('[name=name]').fill('Website Browser Test')
        self.page.locator('[name=email]').fill('test@example.com')
        self.page.locator('[name=company]').fill('Local test team')
        message = 'Please capture this local browser test of the Ribyos contact journey.'
        self.page.locator('[name=message]').fill(message)
        with self.page.expect_response(lambda response: response.url.endswith('/contact-submit.php')) as pending:
            self.page.locator('button[type=submit]').click()
        self.assertEqual(pending.value.status, 202)
        expect(self.page.locator('#form-status')).to_contain_text('queued for delivery')
        expect(self.page.locator('[name=name]')).to_have_value('')
        expect(self.page.locator('button[type=submit]')).to_be_enabled()
        messages = list(self.mail.glob('*.eml'))
        self.assertEqual(len(messages), 1)
        self.assertIn(message, messages[0].read_text())

    def test_contact_endpoint_guards_and_rate_limit(self):
        headers = {'Content-Type': 'application/json'}
        payload = {'name': 'HTTP Test', 'email': 'test@example.com', 'company': 'Test Team',
                   'interest': 'Labs collaboration', 'website': '',
                   'message': 'A local test message. Do not send real email.'}
        cases = [
            (None, {}, 405),
            (b'x=1', {'Content-Type': 'application/x-www-form-urlencoded'}, 415),
            (b'{}', {**headers, 'Sec-Fetch-Site': 'cross-site'}, 403),
            (b'x' * 16385, headers, 413),
            (b'{', headers, 400),
            (b'{}', headers, 422),
            (json.dumps({**payload, 'website': 'spam.example'}).encode(), headers, 422),
            (json.dumps(payload).encode(), headers, 202),
            (b'{}', headers, 422),
            (json.dumps(payload).encode(), headers, 429),
        ]
        for body, request_headers, expected in cases:
            status, response_headers, content = request(self.jengara, '/contact-submit.php', body, request_headers)
            self.assertEqual(status, expected, content)
            self.assertEqual(json.loads(content)['ok'], expected == 202)
            self.assertIn('application/json', response_headers['Content-Type'])
            if expected == 429:
                self.assertEqual(response_headers['Retry-After'], '900')
        messages = list(self.mail.glob('*.eml'))
        self.assertEqual(len(messages), 1)
        message = BytesParser().parsebytes(messages[0].read_bytes())
        self.assertEqual(message['To'], 'hello@jengara.ai')
        self.assertEqual(message['Reply-To'], payload['email'])
        self.assertIn(payload['message'], message.get_payload())


if __name__ == '__main__':
    unittest.main(verbosity=2)
