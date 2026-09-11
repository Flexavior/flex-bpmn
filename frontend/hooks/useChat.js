import { useState } from "react";
import * as api from "../services/api.js";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [processModel, setProcessModel] = useState(null);
  const [bpmn, setBpmn] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendPrompt = async (prompt) => {
    setLoading(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: prompt }]);
    try {
      const res = await api.chat(prompt);
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: `Generated "${res.process.process.name}"` },
      ]);
      setProcessModel(res.process);
      setBpmn(res.bpmn ?? null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages((prev) => [...prev, { role: "ai", text: `Error: ${msg}` }]);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const regenerate = async () => {
    if (!processModel) return;
    try {
      const res = await api.generateBpmn(processModel);
      setBpmn(res.bpmn);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return { messages, processModel, bpmn, loading, error, sendPrompt, regenerate };
}