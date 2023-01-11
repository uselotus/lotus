import create from "zustand";
import { PlanVersionType } from "../types/plan-type";

type VersionStoreState = {
  activeVersion?: PlanVersionType;
  setActiveVersion: (activeVersion: PlanVersionType) => void;
};
const useVersionStore = create<VersionStoreState>((set) => ({
  activeVersion: undefined,
  setActiveVersion: (activeVersion: PlanVersionType) => set({ activeVersion }),
}));

export default useVersionStore;
