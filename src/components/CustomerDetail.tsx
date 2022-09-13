import React, { FC, useEffect, useState } from "react";
import { Button, Form, List, Menu, Modal, Radio, Select, Tag } from "antd";
import { CreateCustomerState } from "./CreateCustomerForm";
import { PlanType } from "../types/plan-type";
import type { MenuProps } from "antd";

const items: MenuProps["items"] = [
  {
    label: "Subscriptions",
    key: "subscriptions",
  },
  {
    label: "History",
    key: "history",
  },
];

interface Props {
  subscriptions: string[];
  plans: PlanType[] | undefined;
}

const subscriptionView: FC<Props> = ({ subscriptions, plans }) => {
  const selectPlan = (plan: PlanType) => {
    // setSelectedPlan(plan);
  };

  if (plans === undefined) {
    return (
      <div>
        <h3 className="text-xl font-main">No Plans Defined!</h3>
      </div>
    );
  }

  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center">
        <h3 className="text-xl font-main">No Subscriptions</h3>
        <p className="font-bold">Choose A Plan to Subscribe To</p>
        <div className=" h-3/6">
          <List>
            {plans.map((plan) => (
              <List.Item>
                <p>{plan.name}</p>
              </List.Item>
            ))}
          </List>
        </div>
      </div>
    );
  }
  return (
    <List>
      {subscriptions.map((subscription) => (
        <List.Item>
          <p>{subscription}</p>
        </List.Item>
      ))}
    </List>
  );
};

const { Option } = Select;

function CustomerDetail(props: {
  visible: boolean;
  onCancel: () => void;
  customer: CreateCustomerState;
  plans: PlanType[] | undefined;
  changePlan: (plan_id: string, customer_id: string) => void;
}) {
  const [form] = Form.useForm();
  const [currentMenu, setCurrentMenu] = useState("subscriptions");

  const onClick: MenuProps["onClick"] = (e) => {
    console.log("click ", e);
    setCurrentMenu(e.key);
  };

  return (
    <Modal
      visible={props.visible}
      title={props.customer.title}
      onCancel={props.onCancel}
    >
      {props.plans === undefined ? (
        <div>Loading...</div>
      ) : (
        <div className="flex justify-between flex-col max-w">
          <div className="text-left	">
            <h2 className="text-2xl font-main mb-3">{props.customer.name}</h2>
            <p>Id: {props.customer.customer_id}</p>
          </div>
          <div className="flex items-center flex-col">
            <Menu
              onClick={onClick}
              selectedKeys={[currentMenu]}
              mode="horizontal"
              items={items}
            />
            <div className="container-lg my-3">
              {(() => {
                switch (currentMenu) {
                  case "subscriptions":
                    return subscriptionView({
                      subscriptions: props.customer.subscriptions,
                      plans: props.plans,
                    });
                  case "history":
                    return <p>History</p>;
                  default:
                    return (
                      <List>
                        {props.customer.subscriptions.map((subscription) => (
                          <List.Item>
                            <Tag color={"default"}>{subscription}</Tag>
                          </List.Item>
                        ))}
                      </List>
                    );
                }
              })()}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default CustomerDetail;
