import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles/app.css";
import "bpmn-js/dist/assets/diagram-js.css";
import "bpmn-js/dist/assets/bpmn-js.css";

createRoot(document.getElementById("root")).render(<App />);
