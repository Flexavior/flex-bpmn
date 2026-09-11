export default function ProcessReview({
  processModel,
  validation,
  source,
  loading,
  onDraw,
}) {
  if (!processModel || source !== "llm") return null;

  const issues = validation?.issues ?? [];
  const isValid = Boolean(validation?.valid);

  return (
    <section className="panel review-panel" aria-labelledby="review-heading">
      <div className="review-heading">
        <div>
          <h2 id="review-heading">Review generated process JSON</h2>
          <p>
            The LLM created this draft. Validation must pass before the
            deterministic generator can draw Camunda-ready BPMN.
          </p>
        </div>
        <span className={`validation-badge ${isValid ? "valid" : "invalid"}`}>
          {isValid ? "Validation passed" : "Validation failed"}
        </span>
      </div>

      <label className="field-label" htmlFor="process-json-review">
        Process JSON
      </label>
      <textarea
        id="process-json-review"
        className="json-review"
        value={JSON.stringify(processModel, null, 2)}
        readOnly
        rows={16}
      />

      <h3>Validator output</h3>
      {issues.length === 0 ? (
        <p className="status status-ok">No validation issues found.</p>
      ) : (
        <ul className="validation-list">
          {issues.map((issue, index) => (
            <li key={`${issue.code}-${index}`} className={`validation-${issue.severity}`}>
              <strong>{issue.severity.toUpperCase()} · {issue.code}</strong>
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="btn-row">
        <button
          className="btn btn-primary"
          type="button"
          onClick={onDraw}
          disabled={!isValid || loading}
        >
          Draw diagram
        </button>
      </div>
    </section>
  );
}
