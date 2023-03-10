/* eslint-disable camelcase */
/* eslint-disable @typescript-eslint/no-non-null-assertion */

import React, { FC } from "react";

import "./SwitchVersions.css";
import { Typography } from "antd";
import { useMutation, useQueryClient } from "react-query";
import { PlanType } from "../../../types/plan-type";
import PlanComponents, { PlanInfo, PlanSummary } from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";

import { Plan } from "../../../api/api";
import PlanRecurringCharges from "./PlanRecurringCharges";
import PlanCustomerSubscriptions from "./PlanCustomerSubscriptions";
import { components } from "../../../gen-types";

interface CustomPlanDetailsProps {
  version: components["schemas"]["PlanDetail"]["versions"][0];
  plan: components["schemas"]["PlanDetail"];
  refetch: VoidFunction;
  activeKey: string;
  createPlanExternalLink: (link: string) => void;
  deletePlanExternalLink: (link: string) => void;
}

// function that takes in a string and returns a string based on the cases of the string equals percentage, flat, or override
function getPriceAdjustmentEnding(
  type: string | undefined,
  amount: number | undefined,
  code: string
) {
  switch (type) {
    case "percentage":
      return `${amount}%`;
    case "fixed":
      return `${code} ${amount}`;
    case "price_override":
      return `${code} ${amount}`;
    default:
      return "No discount added";
  }
}

const CustomPlanDetails: FC<CustomPlanDetailsProps> = ({
  version,
  plan,
  refetch,
  activeKey,
  createPlanExternalLink,
  deletePlanExternalLink,
}) => {
  const queryClient = useQueryClient();

  const createTag = useMutation(
    ({ plan_id, tags }: { plan_id: string; tags: PlanType["tags"] }) =>
      Plan.createTagsPlan(plan_id, {
        tags,
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
      },
    }
  );

  return (
    <div>
      <div className="bg-white mb-6 flex flex-col py-4 px-10 rounded-lg space-y-12">
        <div className="grid gap-12 grid-cols-1 -mx-10 md:grid-cols-3">
          <div className="col-span-1">
            <PlanSummary
              plan={plan}
              createPlanExternalLink={createPlanExternalLink}
              createTagMutation={createTag.mutate}
              deletePlanExternalLink={deletePlanExternalLink}
            />
          </div>
          <div className="col-span-2">
            <PlanInfo activeKey={activeKey} plan={plan} version={version!} />
          </div>
        </div>
        <div className="-mx-10">
          <PlanRecurringCharges recurringCharges={version!.recurring_charges} />
        </div>
        <div className="-mx-10">
          <PlanComponents
            refetch={refetch}
            plan={plan}
            components={version.components}
            alerts={version.alerts}
            plan_version_id={version.version_id}
          />
        </div>
        <div className="-mx-10">
          <PlanFeatures features={version.features} />
        </div>
        <div className=" mt-4 -mx-10 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
          <Typography.Title className="!text-[18px]">
            Price Adjustments:{" "}
            {getPriceAdjustmentEnding(
              version.price_adjustment?.price_adjustment_type,
              version.price_adjustment?.price_adjustment_amount,
              version.currency.symbol
            )}
          </Typography.Title>
        </div>
        <div className="-mx-10">
          <PlanCustomerSubscriptions
            plan_id={plan.plan_id}
            version_id={version!.version_id}
          />
        </div>
      </div>
    </div>
  );
};
export default CustomPlanDetails;
