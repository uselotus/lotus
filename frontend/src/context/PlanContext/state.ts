import { State } from "./types";

const randomName = `experiment-${  Math.random().toString(36).substring(7)}`;

const initialState: State = {
  currentPlan: null,
  currentPlanVersion: null,
  replacementPlan: null,
  replacementPlanVersion: null,
  onSubstitutionChange: null,
  experimentName: randomName,
  dateRange: null,
};

export default initialState;
