#!/usr/bin/env python3

"""
Specific benchmark for Gemma4 TTFT validation

Purpose:
Recover missing Time-To-First-Token (TTFT)
values for gemma4:12b.

Metrics:
- TTFT
- Total latency
- Generated tokens
- Tokens per second
- Load duration

IEEE Access evaluation support
"""


import requests
import json
import time
import csv
from datetime import datetime



# ==============================
# CONFIGURATION
# ==============================


OLLAMA_API = "http://localhost:11434/api/generate"


MODEL = "gemma4:12b"


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


OUTPUT_FILE = "gemma4_ttft_results.csv"



# ==============================
# DEVICE CONFIGURATION
# ==============================


def get_options(device):


    options = {

        "temperature": 0,

        "num_predict": NUM_PREDICT,

        "num_ctx": 4096

    }


    if device == "CPU":

        options["num_gpu"] = 0


    return options



# ==============================
# INFERENCE TEST
# ==============================


def run_inference(device):


    payload = {


        "model": MODEL,

        "prompt": PROMPT,

        "stream": True,

        "options": get_options(device)

    }



    start_time = time.time()


    first_token_time = None


    received_chunks = 0


    final_data = {}



    response = requests.post(

        OLLAMA_API,

        json=payload,

        stream=True,

        timeout=600

    )



    for line in response.iter_lines():


        if not line:

            continue



        current_time = time.time()



        data = json.loads(

            line.decode("utf-8")

        )


        received_chunks += 1



        # ----------------------------------
        # TTFT detection
        # ----------------------------------
        #
        # Some Ollama models do not expose
        # response text immediately.
        # We capture the first valid stream
        # event containing generated content
        # or evaluation metadata.
        # ----------------------------------


        if first_token_time is None:


            if (

                data.get("response")

                or

                data.get("eval_count")

            ):


                first_token_time = current_time




        if data.get("done"):


            final_data = data




    end_time = time.time()



    latency = end_time - start_time



    if first_token_time:

        ttft = (

            first_token_time

            -

            start_time

        )

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


        tps = (

            generated_tokens

            /

            generation_seconds

        )


    else:

        tps = 0




    load_time = (

        final_data.get(

            "load_duration",

            0

        )

        /

        1e9

    )



    return {


        "model": MODEL,

        "device": device,

        "latency_seconds": round(

            latency,

            4

        ),


        "ttft_seconds": (

            round(ttft,4)

            if ttft is not None

            else None

        ),


        "generated_tokens":

            generated_tokens,


        "tokens_per_second":

            round(tps,4),


        "model_load_seconds":

            round(load_time,4),


        "stream_chunks":

            received_chunks


    }





# ==============================
# EXECUTION
# ==============================


results = []



for device in DEVICES:


    print("\n====================")

    print(MODEL)

    print(device)

    print("====================")



    for repetition in range(1, REPETITIONS + 1):


        print(

            "Execution",

            repetition,

            "/",

            REPETITIONS

        )



        result = run_inference(device)



        result["repetition"] = repetition


        result["timestamp"] = datetime.now()



        results.append(result)





# ==============================
# SAVE CSV
# ==============================


with open(

    OUTPUT_FILE,

    "w",

    newline=""

) as file:



    writer = csv.DictWriter(

        file,

        fieldnames=results[0].keys()

    )


    writer.writeheader()


    writer.writerows(results)



print("\n==============================")

print("Finished")

print(

    "File:",

    OUTPUT_FILE

)

print("==============================")