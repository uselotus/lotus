import React from "react";
import planReducer from "./reducer";
import initialState from "./state";
import { State, ActionCreators, ActionTypes } from "./types";
import {
  setCurrentPlan,
  setCurrentPlanVersion,
  setReplacementPlanVersion,
  init,
  setOnSubstitutionChangeFn,
  setReplacementPlan,
  setExperimentName,
  setDateRange,
} from "./actions";
import { PlanType, PlanVersionType } from "../../types/plan-type";

const PlanStateContext = React.createContext<State>(initialState);
const PlanUpdaterContext = React.createContext<ActionCreators>({
  init,
  setCurrentPlan,
  setCurrentPlanVersion,
  setReplacementPlanVersion,
  setReplacementPlan,
  setExperimentName,
  setDateRange,
  setOnSubstitutionChangeFn,
});

interface ProviderProps {
  children: React.ReactNode;
}

export default function PlanProvider({ children }: ProviderProps) {
  const [state, dispatch] = React.useReducer(planReducer, initialState);
  React.useEffect(() => {
    dispatch({ type: ActionTypes.INIT });
  }, []);

  const actions = React.useMemo(
    () => ({
      setCurrentPlan: (data: PlanType | null) => dispatch(setCurrentPlan(data)),
      setReplacementPlan: (data: PlanType | null) =>
        dispatch(setReplacementPlan(data)),
      setOnSubstitutionChangeFn: (data) =>
        dispatch(setOnSubstitutionChangeFn(data)),
      setCurrentPlanVersion: (data: PlanVersionType | null) =>
        dispatch(setCurrentPlanVersion(data)),
      setReplacementPlanVersion: (data: PlanVersionType | null) =>
        dispatch(setReplacementPlanVersion(data)),
      setExperimentName: (data: string | null) =>
        dispatch(setExperimentName(data)),
      setDateRange: (data: string | null) => dispatch(setDateRange(data)),
      init: () => dispatch(init()),
    }),
    []
  );

  return (
    <PlanStateContext.Provider value={state}>
      <PlanUpdaterContext.Provider value={actions}>
        {children}
      </PlanUpdaterContext.Provider>
    </PlanStateContext.Provider>
  );
}

function usePlanState() {
  const state = React.useContext(PlanStateContext);
  if (typeof state === "undefined") {
    throw new Error("usePlanState must be used within a PlanProvider");
  }
  return state;
}

function usePlanUpdater() {
  const actions = React.useContext(PlanUpdaterContext);
  if (typeof actions === "undefined") {
    throw new Error("usePlanUpdater must be used within a PlanProvider");
  }

  return actions;
}

export { PlanProvider, usePlanState, usePlanUpdater };
