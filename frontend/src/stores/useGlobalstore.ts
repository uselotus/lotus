import create from "zustand";
import { OrganizationType } from "../types/account-type";
import { PlanType } from "../types/plan-type";
import { CurrencyType } from "../types/pricing-unit-type";

type GlobalStoreState = {
  username: string;
  org: IOrgStoreType;
  quickStartProgress: IQuickStartStoreType;
  setUsername: (username: string) => void;
  setOrgInfo: (org: IOrgStoreType) => void;
  setQuickStartProgress: (quickStartProgress: IQuickStartStoreType) => void;
};

interface IQuickStartStoreType {
  hasAPIKey: boolean;
  hasTrackedEvent: boolean;
  hasCreatedMetric: boolean;
  hasCreatedPlan: boolean;
  hasPaymentConnected: boolean;
}
interface IOrgStoreType {
  organization_id: string;
  organization_name: string;
  default_currency?: CurrencyType;
  environment?: string;
  plan_tags: PlanType["tags"];
  current_user: { username: string };
  linked_organizations?: OrganizationType["linked_organizations"];
}

const useGlobalStore = create<GlobalStoreState>((set) => ({
  username: "",
  org: {
    organization_id: "",
    organization_name: "N/A",
    default_currency: undefined,
    environment: undefined,
    current_user: { username: "" },
    plan_tags: [],
    linked_organizations: undefined,
  },
  quickStartProgress: {
    hasAPIKey: false,
    hasCreatedMetric: false,
    hasCreatedPlan: false,
    hasPaymentConnected: false,
    hasTrackedEvent: false,
  },
  setUsername: (username: string) => set({ username }),
  setOrgInfo: (org: IOrgStoreType) => set({ org }),
  setQuickStartProgress: (quickStartProgress: IQuickStartStoreType) =>
    set({ quickStartProgress }),
}));
export default useGlobalStore;
export { IOrgStoreType, IQuickStartStoreType, GlobalStoreState };
