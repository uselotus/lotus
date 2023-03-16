/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable camelcase */

import React, { FC } from "react";
import "./PlanDetails.css";
import { Typography } from "antd";
import capitalize from "../../../helpers/capitalize";
import removeUnderscore from "../../../helpers/removeUnderscore";
import { components } from "../../../gen-types";

interface PlanRecurringChargesProps {
  recurringCharges: components["schemas"]["PlanDetail"]["versions"][0]["recurring_charges"];
}

const PlanRecurringCharges: FC<PlanRecurringChargesProps> = ({
  recurringCharges,
}) => (
  <div className="">
    {recurringCharges && recurringCharges.length > 0 ? (
      <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
        <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px]">
          Recurring Charges
        </Typography.Title>
        <div>
          <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
        </div>
        <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
          {recurringCharges.map((recurringCharge) => (
            <div
              key={recurringCharge.name}
              className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px]"
            >
              <div className="pt-4 whitespace-pre-wrap text-base">
                {recurringCharge.name}
              </div>

              <div>
                <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
                <div className="flex items-center  text-card-text justify-between gap-2 mb-1">
                  <div className=" whitespace-nowrap leading-4">Cost</div>{" "}
                  <div className="!text-card-grey">
                    {recurringCharge.pricing_unit.symbol}
                    {recurringCharge.amount}
                  </div>
                </div>

                <div className="flex items-center justify-between text-card-text gap-2 mb-1">
                  <div className=" whitespace-nowrap leading-4">
                    Charge Timing
                  </div>
                  <div className="!text-card-grey">
                    {capitalize(
                      removeUnderscore(recurringCharge.charge_timing)
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between text-card-text gap-2 mb-1">
                  <div className="whitespace-nowrap leading-4">
                    Charge Behavior
                  </div>
                  <div className="!text-card-grey">
                    {capitalize(recurringCharge.charge_behavior)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    ) : (
      <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
        <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px]">
          Recurring Charges
        </Typography.Title>
        <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
        <div className="text-card-grey text-base">
          No recurring charges added
        </div>
      </div>
    )}
  </div>
);
export default PlanRecurringCharges;
