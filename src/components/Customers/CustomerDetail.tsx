import React, { FC, useEffect, useState } from "react";
import { Form, Tabs, Modal, Select } from "antd";
import { CreateCustomerState } from "../CreateCustomerForm";
import { PlanType } from "../../types/plan-type";
import { CreateSubscriptionType } from "../../types/subscription-type";
import LoadingSpinner from "../LoadingSpinner";
import { Customer } from "../../api/api";
import SubscriptionView from "./CustomerSubscriptionView";
import { useMutation } from "react-query";
import dayjs from "dayjs";

const { Option } = Select;

function CustomerDetail(props: {
  visible: boolean;
  onCancel: () => void;
  customer: CreateCustomerState;
  plans: PlanType[] | undefined;
  changePlan: (plan_id: string, customer_id: string) => void;
}) {
  const [form] = Form.useForm();
  const [currentTab, setCurrentTab] = useState("subscriptions");
  const [customerSubscriptions, setCustomerSubscriptions] = useState<string[]>(
    props.customer.subscriptions
  );

  const mutation = useMutation(
    (post: CreateSubscriptionType) => Customer.subscribe(post),
    {
      onSuccess: () => {},
    }
  );

  const addSubscriptions = (subscription: any) => {
    setCustomerSubscriptions([...customerSubscriptions, subscription.name]);
    console.log(subscription, "subscription");
    const today = dayjs().format("YYYY-MM-DD");

    const newSubscription: CreateSubscriptionType = {
      customer_id: props.customer.customer_id,
      billing_plan_id: subscription.billing_plan_id,
      start_date: today,
    };

    mutation.mutate(newSubscription);
  };

  const onClick = (e) => {
    console.log("click ", e);
    setCurrentTab(e.key);
  };

  return (
    <Modal
      visible={props.visible}
      title={props.customer.title}
      onCancel={props.onCancel}
      style={{ width: "80%" }}
    >
      {props.plans === undefined ? (
        <div>
          <LoadingSpinner />
        </div>
      ) : (
        <div className="flex justify-between flex-col max-w">
          <div className="text-left	">
            <h2 className="text-2xl font-main mb-3">{props.customer.name}</h2>
            <p>Id: {props.customer.customer_id}</p>
          </div>
          <div className="flex items-center flex-col">
            <Tabs
              onChange={onClick}
              defaultActiveKey="subscriptions"
              centered
              activeKey={currentTab}
            >
              <Tabs.TabPane disabled={true} tab="Info" key="info">
                Content of Tab Pane 1
              </Tabs.TabPane>
              <Tabs.TabPane tab="Subscriptions" key="subscriptions">
                <SubscriptionView
                  subscriptions={customerSubscriptions}
                  plans={props.plans}
                  onChange={addSubscriptions}
                />
              </Tabs.TabPane>
              <Tabs.TabPane disabled={true} tab="History" key="history">
                <p>History</p>
              </Tabs.TabPane>
            </Tabs>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default CustomerDetail;
