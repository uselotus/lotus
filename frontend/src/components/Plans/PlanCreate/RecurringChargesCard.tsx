/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable camelcase */
import React, { FC } from "react";
import { Typography } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import capitalize from "../../../helpers/capitalize";
import { constructBillType } from "../../Addons/AddonsDetails/AddOnInfo";
import { PlanType } from "../../../types/plan-type";
import { PencilSquareIcon } from "../../base/PencilIcon";

interface RecurringChargesProps {
  recurringCharges: PlanType["display_version"]["recurring_charges"];
  makeEditable: (name: string) => void;
  deleteHandler: (name: string) => void;
}

const RecurringChargesCard: FC<RecurringChargesProps> = ({
  recurringCharges,
  makeEditable,
  deleteHandler,
}) => (
  <div className="grid grid-cols-2 gap-6">
    {recurringCharges.map((recurringCharge) => (
      <div
        key={recurringCharge.name}
        className="min-h-[200px]  min-w-[246px] p-6 cursor-pointer  rounded-sm bg-primary-50  shadow-lg"
        aria-hidden
      >
        <Typography.Title className="pt-4 font-alliance !text-sm">
          <div className="flex items-center">
            <span>{recurringCharge.name}</span>
            <div className="ml-auto flex items-center gap-4">
              <PencilSquareIcon
                onClick={() => makeEditable(recurringCharge.name)}
              />
              <DeleteOutlined
                className="text-xl !text-red-700"
                onClick={() => deleteHandler(recurringCharge.name)}
              />
            </div>
          </div>
        </Typography.Title>

        <div>
          <div>
            <div className="mb-2">
              <div className=" w-full h-[1.5px] mt-6 bg-card-divider" />
            </div>

            <div className="flex items-center text-card-grey justify-between gap-2 mb-1">
              <div className=" font-normal whitespace-nowrap leading-4">
                Cost
              </div>
              <div className="flex gap-1 text-card-text font-alliance">
                {" "}
                <div>{recurringCharge.pricing_unit.symbol}</div>
                <div>{recurringCharge.amount}</div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-grey gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Charge Timing
            </div>
            <div className="text-card-text font-alliance">
              {capitalize(constructBillType(recurringCharge.charge_timing))}
            </div>
          </div>

          <div className="flex items-center justify-between text-card-grey gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Charge Behavior
            </div>
            <div className="text-card-text font-alliance">
              {capitalize(recurringCharge.charge_behavior)}
            </div>
          </div>
        </div>
      </div>
    ))}
  </div>
);
export default RecurringChargesCard;
