import create from "zustand";
import { OrganizationType } from "../types/account-type";
import { PricingUnit } from "../types/pricing-unit-type";
type GlobalStoreState = {
  username: string;
  org: IOrgStoreType;
  setUsername: (username: string) => void;
  setOrgInfo: (org: IOrgStoreType) => void;
};

interface IOrgStoreType {
  organization_id: string;
  company_name: string;
  default_currency?: PricingUnit;
  environment?: string;
}

const useGlobalStore = create<GlobalStoreState>((set) => ({
  username: "",
  org: {
    organization_id: "",
    company_name: "N/A",
    default_currency: undefined,
    environment: undefined,
  },
  setUsername: (username: string) => set({ username }),
  setOrgInfo: (org: IOrgStoreType) => set({ org }),
}));
export default useGlobalStore;
export { IOrgStoreType };
