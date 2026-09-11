import { useId, useState } from "react";

const REASONS = {
  no_api_key: "API key not configured",
  unreachable: "Provider unreachable",
  invalid_key: "API key rejected",
};

export default function PromptBox({
  onSend,
  disabled,
  providers,
  selectedProvider,
  selectedModel,
  onProviderChange,
  onModelChange,
  onRefreshProviders,
}) {
  const [prompt, setPrompt] = useState("");
  const fieldId = useId();
  const providerId = useId();
  const modelId = useId();
  const activeProvider = providers.find((item) => item.name === selectedProvider);
  const canGenerate = Boolean(
    prompt.trim() && activeProvider?.available && selectedModel && !disabled,
  );

  const submit = (e) => {
    e.preventDefault();
    if (canGenerate) {
      onSend(prompt.trim());
      setPrompt("");
    }
  };

  return (
    <form onSubmit={submit}>
      <label className="field-label" htmlFor={fieldId}>
        Describe a process to generate process JSON
      </label>
      <textarea
        id={fieldId}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        maxLength={4000}
        rows={4}
        placeholder="Example: Student enrolls in a course, staff confirm payment, then the system writes the enrollment."
        disabled={disabled}
      />
      <div className="provider-grid">
        <div>
          <label className="field-label" htmlFor={providerId}>Provider</label>
          <select
            id={providerId}
            value={selectedProvider}
            onChange={(event) => onProviderChange(event.target.value)}
            disabled={disabled}
          >
            <option value="">Select an available provider</option>
            {providers.map((provider) => (
              <option
                key={provider.name}
                value={provider.name}
                disabled={!provider.available}
              >
                {provider.name}
                {provider.available
                  ? ""
                  : ` — ${REASONS[provider.reason] ?? provider.reason}`}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor={modelId}>Model</label>
          <select
            id={modelId}
            value={selectedModel}
            onChange={(event) => onModelChange(event.target.value)}
            disabled={disabled || !activeProvider?.available}
          >
            <option value="">Select a model</option>
            {(activeProvider?.models ?? []).map((model) => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </div>
      </div>
      {!providers.some((provider) => provider.available) && (
        <p className="status status-error" role="status">
          Add a remote key in backend/.env or start Ollama.
        </p>
      )}
      <div className="btn-row">
        <button className="btn btn-primary" type="submit" disabled={!canGenerate}>
          Generate process JSON
        </button>
        <button
          className="btn btn-secondary"
          type="button"
          onClick={onRefreshProviders}
          disabled={disabled}
        >
          Refresh availability
        </button>
      </div>
    </form>
  );
}
