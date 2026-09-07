import os
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from arize import ArizeClient


# ============================================================
# 1. LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

ARIZE_API_KEY = os.getenv("ARIZE_AX_API_KEY")
ARIZE_SPACE_ID = os.getenv("ARIZE_AX_SPACE_ID")

if not ARIZE_API_KEY:
    raise ValueError("ARIZE_AX_API_KEY is not set")

if not ARIZE_SPACE_ID:
    raise ValueError("ARIZE_AX_SPACE_ID is not set")


# ============================================================
# 2. CREATE ARIZE CLIENT
# ============================================================

client = ArizeClient(
    api_key=ARIZE_API_KEY
)


# ============================================================
# 3. LOAD CSV
# ============================================================

CSV_PATH = "arize_all_spans.csv"

df = pd.read_csv(CSV_PATH)

print(f"Loaded {len(df)} rows from CSV")


# ============================================================
# 4. PREPARE DATASET
# ============================================================

dataset_df = pd.DataFrame({
    "attributes.input.value": df["input"],
    "attributes.output.value": df["output"],
})


# Keep useful metadata if available
metadata_columns = [
    "context.trace_id",
    "context.span_id",
    "name",
]

for column in metadata_columns:
    if column in df.columns:
        dataset_df[column] = df[column]


# Remove rows without input/output
dataset_df = dataset_df.dropna(
    subset=[
        "attributes.input.value",
        "attributes.output.value",
    ]
).reset_index(drop=True)


print(f"Rows going into evaluation: {len(dataset_df)}")


# ============================================================
# 5. CREATE A UNIQUE DATASET NAME
# ============================================================

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

DATASET_NAME = f"actionability-evaluation-{timestamp}"

print(f"Creating Arize dataset: {DATASET_NAME}")


# ============================================================
# 6. CREATE DATASET IN ARIZE
# ============================================================

dataset = client.datasets.create(
    space=ARIZE_SPACE_ID,
    name=DATASET_NAME,
    examples=dataset_df,
)

print("\nDataset created successfully")
print("Dataset ID:", dataset.id)


# ============================================================
# 7. GET EXISTING ACTIONABILITY EVALUATOR
# ============================================================

arize_evaluator = client.evaluators.get(
    evaluator="Actionability",
    space=ARIZE_SPACE_ID,
)

print("\n" + "=" * 70)
print("EVALUATOR")
print("=" * 70)

print("Name        :", arize_evaluator.name)
print("Evaluator ID:", arize_evaluator.id)
print("Version ID  :", arize_evaluator.version.id)


# ============================================================
# 8. DEFINE TASK
# ============================================================

def task(dataset_row):
    """
    Return the existing model output from the dataset.

    The Actionability evaluator will evaluate this output.
    """

    return dataset_row["attributes.output.value"]


# ============================================================
# 9. RUN EXPERIMENT
# ============================================================

print("\n" + "=" * 70)
print("STARTING ACTIONABILITY EVALUATION")
print("=" * 70)

experiment, results_df = client.experiments.run(
    name=f"actionability-evaluation-{timestamp}",
    dataset=dataset.id,
    task=task,
    evaluators=[
        arize_evaluator
    ],
    concurrency=10,
    exit_on_error=False,
    dry_run=False,
)


# ============================================================
# 10. DISPLAY RESULTS
# ============================================================

print("\n" + "=" * 70)
print("EVALUATION COMPLETE")
print("=" * 70)

print("\nExperiment:")
print(experiment)

print("\nResults:")
print(results_df)


# ============================================================
# 11. SAVE RESULTS LOCALLY
# ============================================================

OUTPUT_PATH = "actionability_evaluation_results.csv"

results_df.to_csv(
    OUTPUT_PATH,
    index=False,
)

print("\nResults saved to:")
print(OUTPUT_PATH)