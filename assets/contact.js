const form=document.querySelector('#inquiry');
if(form){
  const submit=form.querySelector('button[type="submit"]');
  const status=document.querySelector('#form-status');
  let pending=false;
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(pending||!form.reportValidity())return;
    const values=Object.fromEntries(new FormData(form));
    pending=true;
    submit.disabled=true;
    form.setAttribute('aria-busy','true');
    status.textContent='Sending your inquiry…';
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),20000);
    try{
      const response=await fetch(form.action,{
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','Accept':'application/json'},
        body:JSON.stringify(values),signal:controller.signal
      });
      if(!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('Unexpected response');
      const result=await response.json();
      if(response.ok&&result.ok===true){
        status.textContent='Your inquiry has been queued for delivery. Thank you for contacting Jengara.';
        form.reset();
      }else if(response.status===422){
        status.textContent='Please check your name, work email, company and message, then try again. Your message must be between 20 and 2,000 characters.';
      }else if(response.status===429){
        status.textContent='Too many recent attempts. Please wait a while before trying again, or email hello@jengara.ai directly.';
      }else if(response.status===413){
        status.textContent='Your inquiry is too long. Please shorten it and try again.';
      }else{
        status.textContent='We could not confirm your inquiry was queued. Your text is still here. Please try later or email hello@jengara.ai directly.';
      }
    }catch(error){
      status.textContent='We could not confirm whether your inquiry was queued. Your text is still here. Please wait before retrying, or email hello@jengara.ai directly.';
    }finally{
      clearTimeout(timeout);
      pending=false;
      submit.disabled=false;
      form.removeAttribute('aria-busy');
    }
  });
  form.querySelector('fieldset').disabled=false;
}
