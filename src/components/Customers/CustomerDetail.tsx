import React, { FC, useEffect, useState } from "react";
import { Form, Tabs, Modal, Select } from "antd";
import { CreateCustomerState } from "./CreateCustomerForm";
import { PlanType } from "../../types/plan-type";
import { CreateSubscriptionType } from "../../types/subscription-type";
import LoadingSpinner from "../LoadingSpinner";
import { Customer } from "../../api/api";
import SubscriptionView, {
  cancelSubscriptionType,
} from "./CustomerSubscriptionView";
import { useMutation, useQueryClient } from "react-query";
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
  const queryClient = useQueryClient();

  const [currentTab, setCurrentTab] = useState("subscriptions");
  const [customerSubscriptions, setCustomerSubscriptions] = useState<string[]>(
    props.customer.subscriptions
  );

  const mutation = useMutation(
    (post: CreateSubscriptionType) => Customer.subscribe(post),
    {
      onSettled: () => {
        queryClient.invalidateQueries(["customer_list"]);
      },
    }
  );

  const cancelMutation = useMutation(
    (post: cancelSubscriptionType) => Customer.cancelSubscription(post),
    {
      onSettled: () => {
        queryClient.invalidateQueries(["customer_list"]);
      },
    }
  );

  const cancelSubscription = (props: {
    subscription_uid: string;
    bill_now: boolean;
    revoke_access: boolean;
  }) => {
    cancelMutation.mutate(props);
  };

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
    setCurrentTab(e.key);
  };

  return (
    <Modal
      visible={props.visible}
      title={props.customer.title}
      onCancel={props.onCancel}
      okType="default"
      onOk={props.onCancel}
      style={{ width: "80%" }}
      footer={null}
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
                <div key={props.customer.customer_id}>
                  <SubscriptionView
                    key={props.customer.customer_id}
                    subscriptions={customerSubscriptions}
                    plans={props.plans}
                    onChange={addSubscriptions}
                    onCancel={cancelSubscription}
                  />
                </div>
              </Tabs.TabPane>
              <Tabs.TabPane disabled={true} tab="Invoices" key="invoices">
                <p>Invoices</p>
              </Tabs.TabPane>
            </Tabs>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default CustomerDetail;
