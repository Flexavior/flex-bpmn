import { lazy, Suspense } from "react";

const BpmnCanvas = lazy(() => import("./BpmnCanvas.jsx"));

function downloadBpmn(bpmn, name) {
  const blob = new Blob([bpmn], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name ?? "process.bpmn";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function BPMNViewer({
  processModel,
  bpmn,
  loading,
  canDraw = true,
  onRegenerate,
  onDeploy,
  deployNotice,
  status,
}) {
  const name = processModel?.process?.name ?? "BPMN diagram";

  return (
    <section className="panel" aria-labelledby="diagram-heading">
      <div className="btn-row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 id="diagram-heading">{name}</h2>
        <div className="btn-row">
          <button
            className="btn btn-secondary"
            type="button"
            onClick={onRegenerate}
            disabled={!processModel || !canDraw || loading}
          >
            {bpmn ? "Re-render XML" : "Draw diagram"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => downloadBpmn(bpmn, `${processModel?.process?.id ?? "process"}.bpmn`)}
            disabled={!bpmn}
          >
            Download .bpmn
          </button>
          <button className="btn btn-primary" type="button" onClick={onDeploy} disabled={!bpmn || loading}>
            Deploy to Camunda
          </button>
        </div>
      </div>

      {deployNotice && (
        <p
          className={`status ${deployNotice.type === "error" ? "status-error" : "status-ok"}`}
          role={deployNotice.type === "error" ? "alert" : "status"}
        >
          {deployNotice.text}
        </p>
      )}

      {!bpmn && !loading && <p>No diagram yet. Choose a PRD process or generate one.</p>}
      {loading && !deployNotice && (
        <p className="status" role="status">
          {status?.toLowerCase().includes("deploy") ? status : "Updating diagram…"}
        </p>
      )}
      {bpmn && (
        <Suspense fallback={<p role="status">Loading diagram viewer…</p>}>
          <BpmnCanvas xml={bpmn} />
        </Suspense>
      )}
    </section>
  );
}
