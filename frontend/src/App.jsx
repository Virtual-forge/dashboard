import { useState } from "react";
import Login from "./components/Login.jsx";
import Dashboard from "./components/Dashboard.jsx";
import { isLoggedIn, logout, getStoredEmail } from "./api.js";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());

  if (!loggedIn) {
    return <Login onLoggedIn={() => setLoggedIn(true)} />;
  }

  return (
    <Dashboard
      email={getStoredEmail()}
      onLogout={() => {
        logout();
        setLoggedIn(false);
      }}
    />
  );
}
