import { AssistantHost } from "./components/AssistantHost";
import { Sprite } from "./design/Icon";
import { Address } from "./screens/Address";
import { Cart } from "./screens/Cart";
import { Checkout } from "./screens/Checkout";
import { Family } from "./screens/Family";
import { Home } from "./screens/Home";
import { List } from "./screens/List";
import { Pay } from "./screens/Pay";
import { Pdp } from "./screens/Pdp";
import { Settings } from "./screens/Settings";
import { Track } from "./screens/Track";
import { AppProvider, useApp } from "./state";

function Screens() {
  const { route } = useApp();
  // key: each navigation animates in as a fresh screen
  switch (route.screen) {
    case "list":
      return <List key={`list-${route.listCat}-${route.query}`} />;
    case "pdp":
      return <Pdp key={`pdp-${route.pdpId}`} />;
    case "cart":
      return <Cart />;
    case "checkout":
      return <Checkout />;
    case "pay":
      return <Pay />;
    case "track":
      return <Track />;
    case "settings":
      return <Settings />;
    case "family":
      return <Family />;
    case "address":
      return <Address />;
    case "talk":
      // The Talk page is the assistant itself (see AssistantHost); the screen below stays put.
      return <Home />;
    default:
      return <Home />;
  }
}

function Toast() {
  const { toast } = useApp();
  return toast ? (
    <div className="toast" role="status">
      {toast}
    </div>
  ) : null;
}

export function App() {
  return (
    <AppProvider>
      <div className="phone">
        <Sprite />
        <Screens />
        <AssistantHost />
        <Toast />
      </div>
    </AppProvider>
  );
}
