import React, { FC } from "react";
import { PlanType } from "../types/plan-type";

function PlanDisplayBasic(props: { plan: PlanType }) {
  return (
    <div className="space-y-4">
      <div className="flex space-x-4 flex-row items-center ">
        <div className="font-bold text-xl">{props.plan.name}</div>
        <p>{props.plan.description}</p>
      </div>

      <div className="flex flex-row justify-between">
        <p>
          {" "}
          <b>Interval</b>: {props.plan.billing_interval}
        </p>
        <p>
          {" "}
          <b>Recurring Price</b>: {props.plan.flat_rate}
        </p>
        <p>
          {" "}
          <b>Pay In Advance</b>: Yes
        </p>
      </div>
    </div>
  );
}

export default PlanDisplayBasic;
