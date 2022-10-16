import React from "react";
import planReducer from "./reducer";
import InitialState from "./state";
import { State, ActionCreators } from "./types";
import {
  setCurrentPlan,
  init,
  setOnSubstitutionChangeFn,
  setReplacementPlan,
} from "./actions";
import { PlanType } from "../../types/plan-type";

const PlanStateContext = React.createContext<State>(InitialState);
const PlanUpdaterContext = React.createContext<Omit<ActionCreators, "init">>({
  setCurrentPlan: () => {},
  setOnSubstitutionChangeFn: null,
});

interface ProviderProps {
  children: React.ReactNode;
}

export default function PlanProvider({ children }: ProviderProps) {
  const [state, dispatch] = React.useReducer(planReducer, InitialState);
  React.useEffect(() => {
    dispatch(init());
  }, []);

  const actions = React.useMemo(
    () => ({
      setCurrentPlan: (data: PlanType) => dispatch(setCurrentPlan(data)),
      setReplacementPlan: (data: PlanType) =>
        dispatch(setReplacementPlan(data)),
      setOnSubstitutionChangeFn: (data) =>
        dispatch(setOnSubstitutionChangeFn(data)),
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
