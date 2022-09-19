import React, { FC } from "react";
import { PlanType } from "../types/plan-type";
import { Card, Divider, List } from "antd";
import { Plan } from "../api/api";

function PlanDisplayBasic(props: { plan: PlanType }) {
  return (
    <Card className="my-5">
      <div className="space-y-4">
        <div className="flex space-x-4 flex-row items-center ">
          <div className="font-bold text-2xl">{props.plan.name}</div>
        </div>
        <Divider />
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
              <b>Recurring Price</b>: ${props.plan.flat_rate}
            </p>
          </div>
          <p>
            {" "}
            <b>Pay In Advance</b>: Yes
          </p>
        </div>
        <div className="flex">
          <List
            dataSource={props.plan.components}
            renderItem={(item) => (
              <List.Item>
                <Card>
                  <p className="text-base font-main mb-3">
                    Metric: <b>{item.billable_metric.event_name}</b>
                  </p>

                  <p className="font-main">
                    {" "}
                    Aggregation Type:{" "}
                    <b>{item.billable_metric.aggregation_type}</b>
                  </p>
                  <p className="font-main">
                    {" "}
                    Property: <b>{item.billable_metric.property_name}</b>
                  </p>
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
