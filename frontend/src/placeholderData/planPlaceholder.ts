import { PlanDetailType } from "../types/plan-type";

// create empty placeholder object for PlanDetailType
export const planDetailPlaceholder: PlanDetailType = {
  plan_name: "",
  plan_duration: "monthly",
  plan_id: "",
  status: "active",
  created_on: "",
  created_by: "",
  num_versions: 0,
  active_subscriptions: 0,
  versions: [
    {
      description: "",
      plan_id: "",
      flat_fee_billing_type: "",
      flat_rate: 0,
      status: "",
      components: [],
      version: 0,
      version_id: "",
      created_by: "",
      created_on: "",
      active_subscriptions: 0,
      features: [],
      usage_billing_frequency: "monthly",
    },
  ],
};
