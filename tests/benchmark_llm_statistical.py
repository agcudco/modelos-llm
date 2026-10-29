#!/usr/bin/env python3

"""
Benchmark estadístico para Ollama LLM
Métricas:
- TTFT (Time To First Token)
- Latencia total
- Tokens/s
- Repeticiones
- Media
- Desviación estándar
- Intervalo confianza 95%

Compatible con Ollama API.
"""

import requests
import time
import csv
import statistics
import math
from datetime import datetime


# ==============================
# CONFIGURACIÓN
# ==============================

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


MODELS = [
    "phi4:14b",
    "qwen3.8:27b",
    "gemma4:12b"
]


DEVICES = [
    "gpu",
    "cpu"
]


REPETITIONS = 5


PROMPT = """
Explain briefly what characterizes a secure microservices architecture
and mention three security controls.
"""


NUM_PREDICT = 128


OUTPUT_FILE = "llm_benchmark_results.csv"


# ==============================
# CONFIGURAR CPU/GPU
# ==============================


def ollama_options(device):

    options = {

        "temperature":0,
        "num_predict":NUM_PREDICT,
        "num_ctx":2048

    }


    if device == "cpu":

        options["num_gpu"] = 0


    return options



# ==============================
# BENCHMARK STREAMING
# ==============================


def run_inference(model,device):


    payload = {


        "model":model,

        "prompt":PROMPT,

        "stream":True,

        "options":ollama_options(device)

    }


    start=time.time()

    first_token_time=None

    tokens=0

    total_response=""


    response=requests.post(

        OLLAMA_URL,

        json=payload,

        stream=True

    )


    for line in response.iter_lines():


        if line:


            now=time.time()


            if first_token_time is None:

                first_token_time=now



            data=line.decode("utf-8")


            try:

                import json

                chunk=json.loads(data)


                text=chunk.get(
                    "response",
                    ""
                )


                if text:

                    tokens+=1

                    total_response+=text


            except:

                pass



    end=time.time()



    latency=end-start


    if first_token_time:

        ttft=first_token_time-start

    else:

        ttft=None



    tps=tokens/latency if latency>0 else 0



    return {


        "latency":latency,

        "ttft":ttft,

        "tokens":tokens,

        "tps":tps

    }



# ==============================
# ESTADÍSTICA
# ==============================


def confidence_interval(values):


    n=len(values)


    mean=statistics.mean(values)


    if n < 2:

        return mean,0,0,0


    std=statistics.stdev(values)


    margin=1.96*(std/math.sqrt(n))


    return (

        mean,

        std,

        mean-margin,

        mean+margin

    )



# ==============================
# EJECUCIÓN PRINCIPAL
# ==============================


results=[]


for model in MODELS:


    for device in DEVICES:


        print("\n======================")

        print(model,device)

        print("======================")



        latency_values=[]

        ttft_values=[]

        tps_values=[]



        for r in range(REPETITIONS):


            print(
                "Repetición",
                r+1
            )


            result=run_inference(

                model,

                device

            )


            latency_values.append(
                result["latency"]
            )


            ttft_values.append(
                result["ttft"]
            )


            tps_values.append(
                result["tps"]
            )



        latency_stats=confidence_interval(
            latency_values
        )


        ttft_stats=confidence_interval(
            ttft_values
        )


        tps_stats=confidence_interval(
            tps_values
        )



        results.append({


            "timestamp":
            datetime.now(),


            "model":
            model,


            "device":
            device,


            "repetitions":
            REPETITIONS,


            "latency_mean":
            latency_stats[0],


            "latency_std":
            latency_stats[1],


            "latency_ci95_low":
            latency_stats[2],


            "latency_ci95_high":
            latency_stats[3],



            "ttft_mean":
            ttft_stats[0],


            "ttft_std":
            ttft_stats[1],


            "ttft_ci95_low":
            ttft_stats[2],


            "ttft_ci95_high":
            ttft_stats[3],



            "tps_mean":
            tps_stats[0],


            "tps_std":
            tps_stats[1],


            "tps_ci95_low":
            tps_stats[2],


            "tps_ci95_high":
            tps_stats[3]


        })



# ==============================
# GUARDAR CSV
# ==============================


with open(

    OUTPUT_FILE,

    "w",

    newline=""

) as f:


    writer=csv.DictWriter(

        f,

        fieldnames=results[0].keys()

    )


    writer.writeheader()


    writer.writerows(results)



print("\n================================")

print("Benchmark terminado")

print(

    "Resultados:",

    OUTPUT_FILE

)

print("================================")