import {
  Events,
  APIKey,
  Metrics,
  Plan,
  Webhook,
  PaymentProcessorIntegration,
} from "../api/api";
import {
  GlobalStoreState,
  IQuickStartStoreType,
} from "../stores/useGlobalstore";

interface QuickStartCheckProps {
  setQuickStartProgress: (value: IQuickStartStoreType) => void;
}

export const selectQuickStartProgress = (state: GlobalStoreState): number => {
  let totalProgress = 0;
  if (state.quickStartProgress.hasAPIKey) {
    totalProgress += 20;
  }
  if (state.quickStartProgress.hasCreatedMetric) {
    totalProgress += 20;
  }
  if (state.quickStartProgress.hasCreatedPlan) {
    totalProgress += 20;
  }
  if (state.quickStartProgress.hasPaymentConnected) {
    totalProgress += 20;
  }
  if (state.quickStartProgress.hasTrackedEvent) {
    totalProgress += 20;
  }
  return totalProgress;
};

const quickStartCheck = async ({
  setQuickStartProgress,
}: QuickStartCheckProps) => {
  let quickStartCheckResult: IQuickStartStoreType = {
    hasAPIKey: false,
    hasCreatedMetric: false,
    hasCreatedPlan: false,
    hasPaymentConnected: false,
    hasTrackedEvent: false,
  };
  // Check if user has created Api key
  try {
    const apiKeys = await APIKey.getKeys();

    if (apiKeys && apiKeys.length > 0) {
      quickStartCheckResult = { ...quickStartCheckResult, hasAPIKey: true };
    }
  } catch (error) {
    console.log("Error fetching API keys:", error);
  }

  // Check if user has created an event
  try {
    const response = await Events.getEventPreviews("");
    const eventData = response;

    if (eventData && eventData.results && eventData.results.length > 0) {
      quickStartCheckResult = {
        ...quickStartCheckResult,
        hasTrackedEvent: true,
      };
    }
  } catch (error) {
    console.log("Error fetching event data:", error);
  }

  // Check if user has created a metric
  try {
    const metrics = await Metrics.getMetrics();

    if (metrics && metrics.length > 0) {
      quickStartCheckResult = {
        ...quickStartCheckResult,
        hasCreatedMetric: true,
      };
    }
  } catch (error) {
    console.log("Error fetching metrics:", error);
  }

  // Check if user has created a plan
  try {
    const plans = await Plan.getPlans();

    if (plans && plans.length > 0) {
      quickStartCheckResult = {
        ...quickStartCheckResult,
        hasCreatedPlan: true,
      };
    }
  } catch (error) {
    console.log("Error fetching plans:", error);
  }

  // Check if user has connected a payment method or hooked up to a webhook for invoice.created
  try {
    const paymentProcessors =
      await PaymentProcessorIntegration.getPaymentProcessorConnectionStatus();
    if (paymentProcessors && paymentProcessors.length > 0) {
      for (let i = 0; i < paymentProcessors.length; i += 1) {
        if (paymentProcessors[i].connected) {
          quickStartCheckResult = {
            ...quickStartCheckResult,
            hasPaymentConnected: true,
          };
          break;
        }
      }
      const webhooks = await Webhook.getEndpoints();
      if (webhooks && webhooks.length > 0) {
        quickStartCheckResult = {
          ...quickStartCheckResult,
          hasPaymentConnected: true,
        };
      }
    }
  } catch (error) {
    console.log("Error fetching payment processors:", error);
  }
  setQuickStartProgress({ ...quickStartCheckResult });
};

export default quickStartCheck;
