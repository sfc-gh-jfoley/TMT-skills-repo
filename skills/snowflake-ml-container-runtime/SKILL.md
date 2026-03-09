---
name: snowflake-ml-container-runtime
description: "Build ML notebooks for Snowflake Container Runtime. Use when: training ML models in Snowflake Notebooks, using DataConnector, registering models to Snowflake Model Registry, XGBoost/sklearn in Container Runtime. Triggers: ML notebook, train model snowflake, model registry, container runtime ML, DataConnector, Snowflake Notebooks Workspaces."
---

# Snowflake ML Notebook Development (Container Runtime)

Build ML training notebooks that run in Snowflake Notebooks with Container Runtime.

## When to Use

- Training ML models in Snowflake Notebooks (Workspaces)
- Using Container Runtime (CPU or GPU compute pools)
- Registering models to Snowflake Model Registry
- XGBoost, sklearn, LightGBM, PyTorch workflows

## Prerequisites

- Snowflake account with Notebooks enabled
- Container Runtime compute pool (CPU or GPU)
- Database/schema with CREATE MODEL privilege
- Source table with training data

## Workflow

```
Gather Requirements → Select Compute (CPU/GPU) → Build Notebook → Test Cells → Register Model → Verify
```

### Step 1: Gather Requirements

**⚠️ ASK USER** (use `ask_user_question` tool):

1. **Database/Schema**: Where is the training data? Where to register the model?
2. **Table**: Source table name
3. **Target column**: What are we predicting?
4. **Model type**: Classification or regression?
5. **Compute**: CPU or GPU? (use decision chart below)
6. **Version naming**: Auto-generate (recommended) or custom name?

### Step 2: Select Compute Type

| Model/Task | Data Size | Recommendation | Reason |
|------------|-----------|----------------|--------|
| **XGBoost, LightGBM, CatBoost** | < 1M rows | CPU | Tree models are CPU-optimized |
| **XGBoost, LightGBM, CatBoost** | > 10M rows | GPU | GPU acceleration significant at scale |
| **Random Forest, Gradient Boosting** | Any | CPU | sklearn doesn't use GPU |
| **Logistic Regression, SVM, KNN** | Any | CPU | Classical ML, no GPU benefit |
| **Neural Networks (PyTorch/TF)** | Any | GPU | Deep learning requires GPU |
| **Transformers, LLMs, BERT** | Any | GPU | Matrix ops need GPU parallelism |
| **CNN (image classification)** | Any | GPU | Convolutions are GPU-native |
| **Feature engineering** | Any | CPU | Pandas/Snowpark ops, no GPU benefit |
| **Inference (most models)** | Any | CPU | Usually fast enough on CPU |
| **Inference (deep learning)** | High throughput | GPU | Batch inference benefits from GPU |

**Quick Decision:**
```
Deep learning? → GPU
Dataset > 10M rows + XGBoost/LightGBM? → GPU
Otherwise → CPU
```

**Cost:** GPU costs significantly more. Default to CPU unless criteria above are met.

### Step 3: Build Notebook Cells

Generate cells in this order. Label each cell clearly.

**Cell 1: Imports**
```python
# Cell 1: setup_imports
import warnings
warnings.filterwarnings('ignore')

from snowflake.snowpark.context import get_active_session
from snowflake.snowpark import functions as F
from snowflake.ml.data import DataConnector
from snowflake.ml.registry import Registry
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

session = get_active_session()
print(f"[Cell 1] Connected: {session.get_current_database()}.{session.get_current_schema()}")
```

**Cell 2: Set Context**
```python
# Cell 2: set_context
session.use_database("<DATABASE>")
session.use_schema("<SCHEMA>")
print(f"[Cell 2] Context: {session.get_current_database()}.{session.get_current_schema()}")
```

**Cell 3: Load Data**
```python
# Cell 3: load_data
df = session.table("<DATABASE>.<SCHEMA>.<TABLE>")
print(f"[Cell 3] Loaded {df.count()} rows")
df.limit(5).show()
```

**Cell 4+: Feature Engineering**

Use `F.sql_expr()` for ALL string comparisons:
```python
# Cell 4: feature_engineering
df = df.with_column(
    "ENCODED_COL",
    F.when(F.sql_expr("COLUMN = 'Value1'"), 1)
    .when(F.sql_expr("COLUMN IN ('Value2', 'Value3')"), 2)
    .otherwise(0)
)
```

**Cell N: Prepare Training Data**
```python
# Cell N: prepare_data
FEATURE_COLS = ["col1", "col2", "col3"]
LABEL_COL = "target"

ml_df = df.select(FEATURE_COLS + [LABEL_COL]).dropna()
pandas_df = DataConnector.from_dataframe(ml_df).to_pandas()

X = pandas_df[FEATURE_COLS]
y = pandas_df[LABEL_COL]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"[Cell N] Training: {len(X_train)}, Test: {len(X_test)}")
```

**Cell N+1: Train Model**
```python
# Cell N+1: train_model
model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.1,
    random_state=42,
    use_label_encoder=False,
    eval_metric='logloss'
)
model.fit(X_train, y_train)
print("[Cell N+1] Training complete")
```

**Cell N+2: Evaluate**
```python
# Cell N+2: evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)

print(f"Accuracy:  {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1 Score:  {f1:.4f}")
```

**⚠️ STOPPING POINT:** Review metrics with user before registering.

**Cell N+3: Register Model**
```python
# Cell N+3: register_model
reg = Registry(session=session, database_name="<DATABASE>", schema_name="<SCHEMA>")

model_version = reg.log_model(
    model,
    model_name="<MODEL_NAME>",
    # version_name omitted - Snowflake auto-generates
    sample_input_data=X_train.head(10),
    target_platforms=["WAREHOUSE"],  # or ["SNOWPARK_CONTAINER_SERVICES"] for GPU
    metrics={"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}
)

print(f"Model: {model_version.model_name}")
print(f"Version: {model_version.version_name}")
```

### Step 4: Verify Registration

```sql
SHOW MODELS IN SCHEMA <DATABASE>.<SCHEMA>;
SHOW VERSIONS IN MODEL <DATABASE>.<SCHEMA>.<MODEL_NAME>;
```

### Step 5: Test Inference

```python
# Warehouse inference
scored_df = model_version.run(test_df, function_name="predict")
output_col = [c for c in scored_df.columns if c not in test_df.columns][0]
scored_df = scored_df.with_column_renamed(output_col, "PREDICTION")
```

## Critical Patterns

### DO Use

| Pattern | Code |
|---------|------|
| Session | `get_active_session()` |
| Data loading | `DataConnector.from_dataframe(df).to_pandas()` |
| String comparisons | `F.sql_expr("COL = 'value'")` |
| Context | `session.use_database()`, `session.use_schema()` |
| Table reference | Fully qualified: `DB.SCHEMA.TABLE` |
| Version naming | Omit `version_name` (auto-generate) |
| Target platform | `target_platforms=["WAREHOUSE"]` for CPU |

### DO NOT Use

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| `snowflake.ml.modeling.ensemble.*` | Old API, uses stored procs, permission errors | Use OSS XGBoost/sklearn |
| `snowflake.ml._internal.*` | Internal, unstable | Remove import |
| `F.col("COL") == "value"` | Invalid SQL, no quotes | `F.sql_expr("COL = 'value'")` |
| `F.col("COL").isin([...])` | Same quoting issue | `F.sql_expr("COL IN ('a','b')")` |
| `df.to_pandas()` for large data | Not optimized | `DataConnector.from_dataframe(df).to_pandas()` |
| `version_name="v1"` | Conflicts on re-run | Omit, let Snowflake generate |

## Model Registry Options

| Compute | target_platforms | Inference Method |
|---------|-----------------|------------------|
| CPU | `["WAREHOUSE"]` | `model_version.run(df)` |
| GPU | `["SNOWPARK_CONTAINER_SERVICES"]` | Requires `create_service()` first |
| Both | `["WAREHOUSE", "SNOWPARK_CONTAINER_SERVICES"]` | Either method |

**GPU/SPCS requires service creation:**
```python
model_version.create_service(
    service_name="INFERENCE_SERVICE",
    service_compute_pool="GPU_POOL",
    image_repo="DB.SCHEMA.IMAGE_REPO"
)
scored_df = model_version.run(df, function_name="predict", service_name="INFERENCE_SERVICE")
```

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `invalid identifier 'VALUE'` | String not quoted | `F.sql_expr("COL = 'VALUE'")` |
| `ModuleNotFoundError: snowflake.ml._internal` | Internal API | Remove import |
| `not logged for inference in Warehouse` | Missing target | `target_platforms=["WAREHOUSE"]` |
| `service_name argument must be provided` | SPCS needs service | `create_service()` first |
| `Unable to rename column` | Wrong output col | Detect dynamically |
| `UDF permission error` | Old modeling API | Switch to OSS + DataConnector |
| `Model version exists` | Re-running notebook | Omit `version_name` |

## Stopping Points

- ✋ **After Step 1:** Confirm requirements before building
- ✋ **After feature engineering:** Verify no SQL errors
- ✋ **After training:** Review metrics before registry
- ✋ **After registry:** Verify model registered

## Output

Jupyter notebook (.ipynb) with:
1. Labeled cells (Cell 1: setup_imports, etc.)
2. Container Runtime compatible imports
3. DataConnector for data loading
4. OSS model training (XGBoost/sklearn)
5. Model registered to Snowflake Registry
6. Ready for warehouse or SPCS inference

## Success Criteria

- [ ] All cells execute without errors
- [ ] Model metrics are acceptable
- [ ] `SHOW MODELS` shows registered model
- [ ] `SHOW VERSIONS IN MODEL` shows version
- [ ] Test inference returns predictions
