import create from "zustand";
import { components } from "../gen-types";

type GlobalStoreState = {
  username: string;
  org?: components["schemas"]["Organization"];
  environmentType?: "Production" | "Development" | "Demo" | "Internal Demo";
  quickStartProgress: IQuickStartStoreType;
  setUsername: (username: string) => void;
  setOrgInfo: (org: components["schemas"]["Organization"]) => void;
  setQuickStartProgress: (quickStartProgress: IQuickStartStoreType) => void;
  setEnvironmentType: (
    environmentType: "Production" | "Development" | "Demo" | "Internal Demo"
  ) => void;
};

interface IQuickStartStoreType {
  hasAPIKey: boolean;
  hasTrackedEvent: boolean;
  hasCreatedMetric: boolean;
  hasCreatedPlan: boolean;
  hasPaymentConnected: boolean;
}

const useGlobalStore = create<GlobalStoreState>((set) => ({
  username: "",
  org: undefined,
  quickStartProgress: {
    hasAPIKey: false,
    hasCreatedMetric: false,
    hasCreatedPlan: false,
    hasPaymentConnected: false,
    hasTrackedEvent: false,
  },
  environmentType: undefined,
  setUsername: (username: string) => set({ username }),
  setOrgInfo: (org: components["schemas"]["Organization"]) => set({ org }),
  setQuickStartProgress: (quickStartProgress: IQuickStartStoreType) =>
    set({ quickStartProgress }),
  setEnvironmentType: (
    environmentType: "Production" | "Development" | "Demo" | "Internal Demo"
  ) => set({ environmentType }),
}));
export default useGlobalStore;
export { IQuickStartStoreType, GlobalStoreState };
