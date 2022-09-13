import React, { FC } from "react";
import { PlanType } from "../types/plan-type";
import { Card, List } from "antd";
import { Plan } from "../api/api";

function PlanDisplayBasic(props: { plan: PlanType }) {
  return (
    <Card>
      <div className="space-y-4">
        <div className="flex space-x-4 flex-row items-center ">
          <div className="font-bold text-2xl">{props.plan.name}</div>
        </div>
        <p className="text-base">{props.plan.description}</p>

        <div className="grid gap-4 grid-rows-2 justify-between">
          <div className="grid grid-cols-2 flex-col">
            <p>
              <b>Plan id:</b> {props.plan.id}
            </p>
            <p>
              <b>Date Created:</b> {props.plan.time_created}
            </p>
          </div>
          <div className="grid grid-cols-2 flex-col gap-5">
            <p>
              {" "}
              <b>Interval</b>: {props.plan.interval}
            </p>
            <p>
              {" "}
              <b>Recurring Price</b>: {props.plan.flat_rate}
            </p>
          </div>
          <p>
            {" "}
            <b>Pay In Advance</b>: Yes
          </p>
        </div>
        <div className="flex justify-center">
          <List
            dataSource={props.plan.components}
            renderItem={(item) => (
              <List.Item>
                <Card>
                  <b className="text-lg">
                    {item.billable_metric.event_name} --{" "}
                    {item.billable_metric.aggregation_type}
                  </b>
                </Card>
              </List.Item>
            )}
          />
        </div>
      </div>
    </Card>
  );
}

export default PlanDisplayBasic;
