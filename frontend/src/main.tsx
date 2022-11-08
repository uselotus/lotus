import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { BrowserRouter } from "react-router-dom";
import "vite/modulepreload-polyfill";
import "./index.css";
import "./custom.less";
import { QueryClient, QueryClientProvider } from "react-query";
import posthog from "posthog-js";

// Telemetry for Cloud Instances Only
//Only Track Client Autocapture in Cloud Production Instances
if (
  !window.location.href.includes("127.0.0.1") &&
  !window.location.href.includes("localhost") &&
  import.meta.env.VITE_API_URL == "https://api.uselotus.io"
) {
  posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
    api_host: "https://app.posthog.com",
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      refetchOnReconnect: false,
      retry: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);
