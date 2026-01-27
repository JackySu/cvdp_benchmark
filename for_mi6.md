# Run cvdp

1. Set up and source env according to `README.md`

2. Modify `.env` file

```bash
USE_HOST_NETWORK=true  # May as well set this as true 
MI6_BASE_URL=https://api.deepseek.com/  # Replace with customized endpoint
MI6_API_KEY=sk-xxx
MI6_MODEL_ID=deepseek-reasoner
DOCKER_TIMEOUT=2400  # Seconds
DOCKER_TIMEOUT_AGENT=2400  # Seconds
DEEPSEEK_API_KEY=sk-xxx  # for non-agentic tasks
# OPENROUTER_API_KEY=sk-xxx
```

You can take reference to `.env.example`

## Run Agentic tasks

1. Put `mi6` binary at `${PROJECT_ROOT}/bin/mi6`

2. Build Docker image

```bash
export AGENT_IMAGE_NAME=mi6_code_agent
export AGENT_IMAGE_TAG=latest
cd agents/mi6_code_agent
./build.sh $AGENT_IMAGE_NAME $AGENT_IMAGE_TAG
cd -
```

3. Run Benchmark

```bash
./run_benchmark.py -f example_dataset/cvdp_v1.0.2_agentic_code_generation_no_commercial.jsonl \  # or commercial 
    -l \
    -p ${your_report_dir} \
    -g ${AGENT_IMAGE_NAME}:${AGENT_IMAGE_TAG}
```

## Run Non-agentic tasks

```bash
./run_benchmark.py -f example_dataset/cvdp_v1.0.2_nonagentic_code_generation_no_commercial.jsonl \  # or commercial
    -l -m ${model_name} \
    -c ./openrouter_deepseek_factory.py \
    -p ${your_report_dir}
```

