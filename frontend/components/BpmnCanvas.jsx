import { useEffect, useRef } from "react";

export default function BpmnCanvas({ xml }) {
  const host = useRef(null);

  useEffect(() => {
    let viewer;
    let cancelled = false;

    async function mount() {
      const { default: NavigatedViewer } = await import("bpmn-js/lib/NavigatedViewer");
      if (cancelled || !host.current) return;
      host.current.innerHTML = "";
      viewer = new NavigatedViewer({ container: host.current });
      if (!xml) return;
      await viewer.importXML(xml);
      viewer.get("canvas").zoom("fit-viewport");
    }

    mount().catch(() => {
      if (host.current) {
        host.current.textContent = "The BPMN XML could not be drawn.";
      }
    });

    return () => {
      cancelled = true;
      if (viewer) viewer.destroy();
    };
  }, [xml]);

  return (
    <div
      ref={host}
      className="canvas-host"
      role="img"
      aria-label="BPMN process diagram"
    />
  );
}
