import { Typography } from "antd";
import React from "react";
import { components } from "../../gen-types";
import capitalize from "../../helpers/capitalize";
import removeUnderscore from "../../helpers/removeUnderscore";

interface Props {
  recurringCharges: components["schemas"]["PlanDetail"]["versions"][0]["recurring_charges"];
}

const RecurringChargesDisplay = ({ recurringCharges }: Props) => (
  <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
    {recurringCharges.map((recurringCharge) => (
      <div
        key={recurringCharge.name}
        className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px]"
      >
        <Typography.Title
          className="pt-4 whitespace-pre-wrap !text-[18px]"
          level={2}
        >
          {recurringCharge.name}
        </Typography.Title>

        <div>
          <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">Cost</div>{" "}
            <div className="!text-card-text">
              {recurringCharge.pricing_unit.symbol}
              {recurringCharge.amount}
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Charge Timing
            </div>
            <div className="!text-card-grey ">
              {capitalize(removeUnderscore(recurringCharge.charge_timing))}
            </div>
          </div>

          <div className="flex items-center justify-between text-card-textgap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Charge Behavior
            </div>
            <div className="!text-card-text">
              {capitalize(recurringCharge.charge_behavior)}
            </div>
          </div>
        </div>
      </div>
    ))}
  </div>
);

export default RecurringChargesDisplay;
