import React, { FC } from "react";
import { PlanType } from "../types/plan-type";
import { Card, Menu, Dropdown, List, Statistic } from "antd";
import { Plan } from "../api/api";

function PlanDisplayBasic(props: { plan: PlanType }) {
  const planMenu = (
    <Menu>
      <Menu.Item key="0">
        <a href="#">Edit</a>
      </Menu.Item>
      <Menu.Item key="1" disabled={props.plan.active_subscriptions !== 0}>
        <a href="#">Delete</a>
      </Menu.Item>
    </Menu>
  );

  return (
    <Card
      className="my-5 w-full"
      extra={
        <Dropdown overlay={planMenu} trigger={["click"]}>
          <a className="text-lg font-bold" onClick={(e) => e.preventDefault()}>
            ... <i className="fas fa-ellipsis-v"></i>
          </a>
        </Dropdown>
      }
      title={
        <div className="flex space-x-4 flex-row items-center space-y-4">
          <h2>{props.plan.name}</h2>
        </div>
      }
    >
      <div className="grid grid-cols-3 justify-items-stretch font-main">
        <div className="space-y-4">
          <p className="text-base">{props.plan.description}</p>

          <div className="grid gap-4 grid-rows-3 justify-between">
            <div className="flex-col">
              <p>
                <b>Plan id:</b> {props.plan.billing_plan_id}
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
            <div className="grid grid-cols-2 gap-5">
              <p>
                <b>Date Created:</b> {props.plan.time_created}
              </p>
              <p>
                {" "}
                <b>Pay In Advance</b>: Yes
              </p>
            </div>
          </div>
        </div>
        <div className="flex self-center">
          {/* <Dropdown
          <List
            className="flex flex-row w-full"
            dataSource={props.plan.components}
            renderItem={(item) => (
              <List.Item className="w-full">
                <Card>
                  <p className="text-base font-main mb-2">
                    Metric: <b>{item.billable_metric.event_name}</b>
                  </p>

                  <p className="font-main">
                    {" "}
                    Cost: ${item.cost_per_batch} per{" "}
                    {item.metric_units_per_batch}
                  </p>
                  <p className="font-main">
                    {" "}
                    Free Units: <b>{item.free_metric_units}</b>
                  </p>
                </Card>
              </List.Item>
            )}
          /> */}
        </div>
        <div className="justify-self-center self-center">
          <div className="font-main font-bold text-4xl text-center">
            {props.plan.active_subscriptions}
          </div>
          <h3>Active Subscriptions</h3>
        </div>
      </div>
    </Card>
  );
}

export default PlanDisplayBasic;
