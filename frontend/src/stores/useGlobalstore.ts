import create from "zustand";
import { OrganizationType } from "../types/account-type";
import { PlanType } from "../types/plan-type";
import { PricingUnit } from "../types/pricing-unit-type";
type GlobalStoreState = {
  username: string;
  org: IOrgStoreType;
  setUsername: (username: string) => void;
  setOrgInfo: (org: IOrgStoreType) => void;
};

interface IOrgStoreType {
  organization_id: string;
  organization_name: string;
  default_currency?: PricingUnit;
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
  setUsername: (username: string) => set({ username }),
  setOrgInfo: (org: IOrgStoreType) => set({ org }),
}));
export default useGlobalStore;
export { IOrgStoreType };
