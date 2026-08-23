STEP-BY-STEP: Create Bedrock Evaluation Job

=== STEP 1: Create the Job ===

1. In the AWS Console, stay on the "Create automatic evaluation" page
2. At the top, verify:
   - Job name: customer-support-chatbot-eval-v3
   - Evaluation type: BYOI (Bring Your Own Input)

3. Click "Next" to proceed to dataset configuration

---

=== STEP 2: Configure Dataset ===

4. Under "Input dataset":
   - Select: S3 URI
   - Enter: s3://udacity-agentic-engineer-c1-eval-608282429299/eval_dataset_v3.jsonl

5. Click "Next" to proceed to evaluator configuration

---

=== STEP 3: Configure Evaluator ===

6. Under "Evaluator model":
   - Select: amazon.nova-pro-v1:0

7. Under "IAM role":
   - Enter: arn:aws:iam::608282429299:role/bedrock-eval-role

8. Click "Next" to proceed to metric configuration

---

=== STEP 4: Select Metrics ===

You should already have these selected from your screenshot:

✅ QUALITY METRICS (8/9):
   - [x] Helpfulness
   - [x] Correctness
   - [x] Faithfulness
   - [x] Completeness
   - [x] Relevance
   - [x] Readability
   - [x] Professional style and tone
   - [x] Following instructions
   - [ ] Coherence (leave unchecked)

✅ RESPONSIBLE AI METRICS (1/3):
   - [x] Harmfulness
   - [ ] Refusal (leave unchecked)

---

=== STEP 5: Add Custom Metric (Fluency) ===

9. Scroll down and click "Add custom metric" or "Add metric"

10. Fill in the custom metric form:

    Metric name: fluency

    Instructions (copy exactly):
    You are evaluating the FLUENCY of a customer support response. Score based on how natural, readable, and well-structured the response is.

    Rules:
    - Look for natural sentence flow and proper grammar
    - Penalize choppy, disjointed, or template-like phrasing
    - Check that the response reads like a real human wrote it
    - Ignore factual accuracy (that's measured separately)
    - Focus on writing quality and readability

    Focus: Does the response read naturally and fluently?

    Variable:
    - Click "Add variable"
    - Name: prediction
    - Source: Leave blank (it auto-pulls from modelResponses[0].response)

    Output schema:
    - Scale type: Numerical
    - Add 4 rows:

      Row 1: Value = 0, Label = Unintelligible, Description = Response is garbled, incomplete, or unreadable
      Row 2: Value = 1, Label = Poor, Description = Response is difficult to follow with awkward phrasing
      Row 3: Value = 2, Label = Acceptable, Description = Response is understandable but has noticeable flaws
      Row 4: Value = 3, Label = Excellent, Description = Response is natural, smooth, and professionally written

    Click "Save" or "Add" to confirm the metric

---

=== STEP 6: Finalize & Create ===

11. Verify all settings:
    - Dataset: s3://udacity-agentic-engineer-c1-eval-608282429299/eval_dataset_v3.jsonl
    - Model: amazon.nova-pro-v1:0
    - Role: arn:aws:iam::608282429299:role/bedrock-eval-role
    - Metrics: 9 total (8 built-in + 1 custom fluency)

12. Click "Create evaluation job"

---

=== STEP 7: Monitor Progress ===

13. After creation, you'll be taken to the evaluations list
14. Click on your job "customer-support-chatbot-eval-v3"
15. Wait for status to change from "Creating" -> "Running" -> "Completed"
16. Once completed, click into the job to view results

Expected completion time: 5-10 minutes for 19 test cases

---

NOTES:

- If you get any errors about permissions, double-check the IAM role ARN
- The dataset has 19 records covering all test cases
- Results will show scores 0-3 for each metric
- Aim for overall average > 2.5 (Good) or > 2.7 (Excellent)
