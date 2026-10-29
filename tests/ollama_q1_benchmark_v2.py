#!/usr/bin/env python3

"""
Ollama Benchmark for IEEE Access

Metrics:
- TTFT (Time To First Token)
- Total latency
- Real generated tokens
- Tokens per second
- Model loading time
- CPU/GPU comparison
- Multiple repetitions
"""


import requests
import json
import time
import csv
from datetime import datetime



# ===============================
# CONFIGURATION
# ===============================


OLLAMA_API = "http://localhost:11434/api/generate"


MODELS = [

    "phi4:14b",
    "qwen3.8:27b",
    "gemma4:12b"

]


DEVICES = [

    "GPU",
    "CPU"

]


REPETITIONS = 5


NUM_PREDICT = 256


PROMPT = """

Explain the advantages and challenges of deploying
large language models in decentralized environments.

Provide a concise technical explanation.

"""


OUTPUT_FILE = "ollama_q1_benchmark_results_v2.csv"



# ===============================
# HARDWARE OPTIONS
# ===============================


def ollama_options(device):


    options = {

        "temperature":0,

        "num_predict":NUM_PREDICT,

        "num_ctx":4096

    }


    if device == "CPU":

        options["num_gpu"] = 0


    return options



# ===============================
# SINGLE TEST
# ===============================


def run_test(model, device):


    payload = {


        "model": model,

        "prompt": PROMPT,

        "stream": True,

        "options": ollama_options(device)

    }



    start = time.time()


    first_token_time = None


    response_text = ""



    final_data = {}



    try:


        response = requests.post(

            OLLAMA_API,

            json=payload,

            stream=True,

            timeout=600

        )


        for line in response.iter_lines():


            if not line:

                continue



            now = time.time()



            data = json.loads(

                line.decode("utf-8")

            )



            # -------------------------
            # Capture first token
            # -------------------------


            token_piece = data.get(

                "response",

                ""

            )


            if token_piece:


                response_text += token_piece



                if first_token_time is None:

                    first_token_time = now




            # -------------------------
            # Final statistics
            # -------------------------


            if data.get("done"):


                final_data = data




        end = time.time()



        # ===========================
        # Metrics
        # ===========================


        latency = end - start



        if first_token_time:

            ttft = first_token_time - start

        else:

            ttft = None



        generated_tokens = final_data.get(

            "eval_count",

            0

        )



        eval_duration = final_data.get(

            "eval_duration",

            0

        )



        if eval_duration > 0:


            generation_seconds = (

                eval_duration / 1e9

            )


            tokens_per_second = (

                generated_tokens /

                generation_seconds

            )


        else:

            tokens_per_second = 0




        load_seconds = (

            final_data.get(

                "load_duration",

                0

            ) / 1e9

        )



        prompt_tokens = final_data.get(

            "prompt_eval_count",

            0

        )



        return {


            "model":model,

            "device":device,

            "latency_seconds":round(

                latency,

                4

            ),


            "ttft_seconds":

                round(ttft,4)

                if ttft else None,



            "generated_tokens":

                generated_tokens,



            "tokens_per_second":

                round(

                    tokens_per_second,

                    4

                ),



            "model_load_seconds":

                round(

                    load_seconds,

                    4

                ),



            "prompt_tokens":

                prompt_tokens


        }




    except Exception as e:


        return {


            "model":model,

            "device":device,

            "latency_seconds":None,

            "ttft_seconds":None,

            "generated_tokens":0,

            "tokens_per_second":0,

            "model_load_seconds":None,

            "prompt_tokens":0,

            "error":str(e)

        }





# ===============================
# EXECUTION
# ===============================


results=[]



for model in MODELS:


    for device in DEVICES:



        print("\n====================")

        print(model)

        print(device)

        print("====================")



        for rep in range(1,REPETITIONS+1):


            print(

                "Execution",

                rep,

                "/",

                REPETITIONS

            )



            result = run_test(

                model,

                device

            )


            result["repetition"] = rep


            result["timestamp"] = (

                datetime.now()

            )



            results.append(result)





# ===============================
# SAVE CSV
# ===============================


with open(

    OUTPUT_FILE,

    "w",

    newline=""

) as f:



    writer = csv.DictWriter(

        f,

        fieldnames=results[0].keys()

    )


    writer.writeheader()


    writer.writerows(results)



print("\n================================")

print("Benchmark finished")

print(

    "Output:",

    OUTPUT_FILE

)

print("================================")