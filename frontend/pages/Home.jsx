import { useStudio } from "../hooks/useStudio.js";
import PromptBox from "../components/PromptBox.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import BPMNViewer from "../components/BPMNViewer.jsx";
import ProcessReview from "../components/ProcessReview.jsx";

export default function Home() {
  const studio = useStudio();

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to diagram
      </a>
      <header className="app-header">
        <h1>FXV BPMN Studio</h1>
        <p>
          LMS and exam workflows for teacher, student, and admin staff. Open a PRD
          process to draw the Camunda-ready diagram, or describe a new process.
          Generated models are drafts until you review them.
        </p>
        <p className="status" role="status">
          {studio.status}
        </p>
      </header>
      <div className="app-shell">
        <aside className="panel" aria-label="Process catalog">
          <h2>PRD processes</h2>
          <ul className="catalog-list">
            {studio.catalog.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="catalog-item"
                  aria-current={studio.activeId === item.id ? "true" : undefined}
                  onClick={() => studio.openCatalog(item.id)}
                  disabled={studio.loading}
                >
                  <strong>
                    {item.prd}: {item.title}
                  </strong>
                  <div className="roles">
                    {(item.roles ?? []).map((role) => (
                      <span className="role" key={role}>
                        {role}
                      </span>
                    ))}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          <PromptBox
            onSend={studio.sendPrompt}
            disabled={studio.loading}
            providers={studio.providers}
            selectedProvider={studio.selectedProvider}
            selectedModel={studio.selectedModel}
            onProviderChange={studio.selectProvider}
            onModelChange={studio.setSelectedModel}
            onRefreshProviders={studio.refreshProviders}
          />
          {studio.error && (
            <p className="status status-error" role="alert">
              {studio.error}
            </p>
          )}
          <ChatPanel messages={studio.messages} />
        </aside>
        <main id="main">
          <ProcessReview
            processModel={studio.processModel}
            validation={studio.validation}
            source={studio.source}
            loading={studio.loading}
            onDraw={studio.drawDiagram}
          />
          <BPMNViewer
            processModel={studio.processModel}
            bpmn={studio.bpmn}
            loading={studio.loading}
            canDraw={studio.validation?.valid}
            onRegenerate={studio.drawDiagram}
            onDeploy={studio.deployModel}
            deployNotice={studio.deployNotice}
            status={studio.status}
          />
        </main>
      </div>
    </>
  );
}
