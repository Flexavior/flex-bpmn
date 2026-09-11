export default function ChatPanel({ messages }) {
  return (
    <section aria-label="Generation log">
      <h2>Log</h2>
      {messages.length === 0 && <p>Select a PRD process or describe one to begin.</p>}
      <div className="chat-log">
        {messages.map((m, i) => (
          <div key={`${m.role}-${i}`} className={m.role === "user" ? "chat-user" : "chat-ai"}>
            <strong>{m.role === "user" ? "You" : "Studio"}: </strong>
            {m.text}
          </div>
        ))}
      </div>
    </section>
  );
}
