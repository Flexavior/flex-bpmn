import { useEffect, useState } from "react";
import * as api from "../services/api.js";

export function useStudio() {
  const [catalog, setCatalog] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [activeId, setActiveId] = useState(null);
  const [processModel, setProcessModel] = useState(null);
  const [validation, setValidation] = useState(null);
  const [source, setSource] = useState(null);
  const [bpmn, setBpmn] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deployNotice, setDeployNotice] = useState(null);
  const [status, setStatus] = useState("Checking API…");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await api.health();
        const [listing, providerData] = await Promise.all([
          api.listCatalog(),
          api.listProviders(),
        ]);
        if (cancelled) return;
        setStatus("API ready");
        setCatalog(listing.items ?? []);
        applyProviders(providerData.providers ?? []);
        if (listing.items?.[0]?.id) {
          await openCatalog(listing.items[0].id);
        }
      } catch (e) {
        if (!cancelled) {
          setStatus("API offline");
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const applyProviders = (items) => {
    setProviders(items);
    const first = items.find((item) => item.available && item.models?.length);
    if (first) {
      setSelectedProvider(first.name);
      setSelectedModel(first.models[0]);
    } else {
      setSelectedProvider("");
      setSelectedModel("");
    }
  };

  const refreshProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listProviders();
      applyProviders(result.providers ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const selectProvider = (name) => {
    setSelectedProvider(name);
    const provider = providers.find((item) => item.name === name);
    setSelectedModel(provider?.models?.[0] ?? "");
  };

  const openCatalog = async (id) => {
    setLoading(true);
    setError(null);
    setDeployNotice(null);
    try {
      const res = await api.getCatalogItem(id);
      setActiveId(id);
      setProcessModel(res.process);
      setValidation({ valid: true, issues: [] });
      setSource("catalog");
      setBpmn(res.bpmn ?? null);
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: `Loaded PRD process ${res.process.process.name}` },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const sendPrompt = async (prompt) => {
    setLoading(true);
    setError(null);
    setStatus(`Calling ${selectedProvider}/${selectedModel}…`);
    setMessages((prev) => [...prev, { role: "user", text: prompt }]);
    try {
      const res = await api.chat(prompt, selectedProvider, selectedModel);
      setProcessModel(res.process);
      setValidation(res.validation);
      setSource("llm");
      setBpmn(null);
      setActiveId(res.process.process.id);
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          text: `Generated “${res.process.process.name}” with ${selectedProvider}/${selectedModel}. Review validation before drawing.`,
        },
      ]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setMessages((prev) => [...prev, { role: "ai", text: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
      setStatus("API ready");
    }
  };

  const drawDiagram = async () => {
    if (!processModel || !validation?.valid) return;
    setLoading(true);
    setError(null);
    setStatus("Drawing validated BPMN…");
    try {
      const res = await api.generateBpmn(processModel);
      setBpmn(res.bpmn);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setStatus("API ready");
    }
  };

  const deployModel = async () => {
    if (!bpmn || !processModel) return;
    setLoading(true);
    setError(null);
    setDeployNotice(null);
    setStatus("Deploying to Camunda…");
    try {
      const result = await api.deploy(processModel.process.id, bpmn);
      const key = result.deployment?.deploymentKey;
      const okText = key
        ? `Deployed “${processModel.process.name}” to Camunda (deployment key ${key}).`
        : `Deployed “${processModel.process.name}” to Camunda.`;
      setDeployNotice({ type: "ok", text: okText });
      setMessages((prev) => [...prev, { role: "ai", text: okText }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setDeployNotice({ type: "error", text: msg });
      setError(msg);
      setMessages((prev) => [...prev, { role: "ai", text: `Deploy failed: ${msg}` }]);
    } finally {
      setLoading(false);
      setStatus("API ready");
    }
  };

  return {
    catalog,
    providers,
    selectedProvider,
    selectedModel,
    activeId,
    processModel,
    validation,
    source,
    bpmn,
    messages,
    loading,
    error,
    deployNotice,
    status,
    selectProvider,
    setSelectedModel,
    refreshProviders,
    openCatalog,
    sendPrompt,
    drawDiagram,
    deployModel,
  };
}
