"""Locust: carga HTTP a Ollama, con conteo de concurrencia efectiva."""
import json, os, threading, time
from locust import HttpUser, constant, task, events

MODEL=os.getenv('OLLAMA_MODEL','phi4:14b')
DEVICE=os.getenv('OLLAMA_DEVICE','gpu')
WAIT=float(os.getenv('WAIT_SECONDS','1'))
NUM_CTX=int(os.getenv('NUM_CTX','2048'))
NUM_PREDICT=int(os.getenv('NUM_PREDICT','128'))
TIMEOUT=float(os.getenv('REQUEST_TIMEOUT','900'))
PROMPT=os.getenv('OLLAMA_PROMPT','Explica en no más de 80 palabras qué caracteriza a una arquitectura de microservicios segura y menciona tres controles de seguridad.')
lock=threading.Lock()
active=0
peak=0
started=0
completed=0
failed=0
samples=[]

@events.test_start.add_listener
def reset(environment, **kwargs):
    global active,peak,started,completed,failed,samples
    with lock:
        active=peak=started=completed=failed=0
        samples=[]

class OllamaUser(HttpUser):
    wait_time=constant(WAIT)
    @task
    def generate(self):
        global active,peak,started,completed,failed
        options={'num_ctx':NUM_CTX,'num_predict':NUM_PREDICT,'temperature':0}
        if DEVICE=='cpu': options['num_gpu']=0
        payload={'model':MODEL,'prompt':PROMPT,'stream':False,'keep_alive':'10m','options':options}
        with lock:
            active+=1; started+=1; peak=max(peak,active)
        ok=False
        try:
            with self.client.post('/api/generate',json=payload,name='ollama_generate',catch_response=True,timeout=TIMEOUT) as response:
                try:
                    data=response.json()
                    if response.status_code!=200 or data.get('error') or not data.get('done'):
                        response.failure('HTTP/JSON/Ollama invalid response')
                    else:
                        response.success(); ok=True
                except (ValueError,TypeError):
                    response.failure('Invalid JSON')
        finally:
            with lock:
                active-=1
                if ok: completed+=1
                else: failed+=1

@events.test_stop.add_listener
def save_counts(environment, **kwargs):
    import csv
    out=os.getenv('COUNTS_CSV','counts.csv')
    with lock:
        values=[MODEL,DEVICE,started,completed,failed,active,peak]
    with open(out,'w',newline='') as f:
        w=csv.writer(f);w.writerow(['model','device','started','completed','failed','active_at_stop','peak_in_flight']);w.writerow(values)
