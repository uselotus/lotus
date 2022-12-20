import create from "zustand";
type GlobalStoreState = {
  username: string;
  org: IOrg;
  setUsername: (username: string) => void;
  setOrgInfo: (org: IOrg) => void;
};
interface IOrg {
  company_name: string;
  currency: string;
  environment?: string;
}

const useGlobalStore = create<GlobalStoreState>((set) => ({
  username: "",
  org: {
    company_name: "",
    currency: "",
    environment: undefined,
  },
  setUsername: (username: string) => set({ username }),
  setOrgInfo: (org: IOrg) => set({ org }),
}));
export default useGlobalStore;
