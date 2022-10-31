import React, { FC, Fragment, useEffect, useState } from "react";
import { PlanType } from "../../types/plan-type";
import {
  Card,
  List,
  Form,
  Select,
  Button,
  Dropdown,
  Menu,
  Statistic,
  Cascader,
} from "antd";
import type { DefaultOptionType } from "antd/es/cascader";
import {
  CreateSubscriptionType,
  TurnSubscriptionAutoRenewOffType,
  ChangeSubscriptionPlanType,
  CancelSubscriptionType,
} from "../../types/subscription-type";
//import the Customer type from the api.ts file
import { Customer, Plan } from "../../api/api";
import dayjs from "dayjs";

import { CustomerDetailSubscription } from "../../types/customer-type";

interface Props {
  customer_id: string;
  subscriptions: CustomerDetailSubscription[];
  plans: PlanType[] | undefined;
  onAutoRenewOff: (
    subscription_id: string,
    props: TurnSubscriptionAutoRenewOffType
  ) => void;
  onCancel: (subscription_id: string, props: CancelSubscriptionType) => void;
  onPlanChange: (
    subscription_id: string,
    props: ChangeSubscriptionPlanType
  ) => void;
  onCreate: (props: CreateSubscriptionType) => void;
}

const filter = (inputValue: string, path: DefaultOptionType[]) =>
  (path[0].label as string).toLowerCase().indexOf(inputValue.toLowerCase()) >
  -1;

const displayRender = (labels: string[]) => labels[labels.length - 1];

interface PlanOption {
  value: string;
  label: string;
  children?: ChangeOption[];
  disabled?: boolean;
}

interface ChangeOption {
  value:
    | "change_subscription_plan"
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill";
  label: string;
  disabled?: boolean;
}

const SubscriptionView: FC<Props> = ({
  customer_id,
  subscriptions,
  plans,
  onCancel,
  onAutoRenewOff,
  onPlanChange,
  onCreate,
}) => {
  const [selectedPlan, setSelectedPlan] = useState<string>();
  const [form] = Form.useForm();

  const [idtoPlan, setIDtoPlan] = useState<{ [key: string]: PlanType }>({});
  const [planList, setPlanList] =
    useState<{ label: string; value: string }[]>();

  const selectPlan = (plan_id: string) => {
    setSelectedPlan(plan_id);
  };

  const cancelAndBill = () => {
    onCancel(subscriptions[0].subscription_id, {
      status: "ended",
      replace_immediately_type: "end_current_subscription_and_bill",
    });
  };

  const cancelAndDontBill = () => {
    onCancel(subscriptions[0].subscription_id, {
      status: "ended",
      replace_immediately_type: "end_current_subscription_dont_bill",
    });
  };

  const turnAutoRenewOff = () => {
    onAutoRenewOff(subscriptions[0].subscription_id, {
      auto_renew: false,
    });
  };

  useEffect(() => {
    if (plans !== undefined) {
      const planMap = plans.reduce((acc, plan) => {
        acc[plan.plan_id] = plan;
        return acc;
      }, {} as { [key: number]: PlanType });
      setIDtoPlan(planMap);
      const newplanList: { label: string; value: string }[] = plans.reduce(
        (acc, plan) => {
          if (
            plan.target_customer === null ||
            plan.target_customer?.customer_id === customer_id
          ) {
            acc.push({ label: plan.plan_name, value: plan.plan_id });
          }
          return acc;
        },
        [] as { label: string; value: string }[]
      );
      setPlanList(newplanList);
    }
  }, [plans]);

  const cancelMenu = (
    <Menu
      items={[
        {
          label: (
            <span onClick={() => cancelAndBill()}>Cancel and Bill Now</span>
          ),
          key: "0",
        },
        {
          label: (
            <span onClick={() => cancelAndDontBill()}>
              Cancel Without Billing
            </span>
          ),
          key: "1",
        },
        {
          label: <span onClick={() => turnAutoRenewOff()}>Cancel Renewal</span>,
          key: "2",
        },
      ]}
    />
  );

  const plansWithSwitchOptions = planList?.reduce((acc, plan) => {
    if (plan.label !== subscriptions[0]?.billing_plan_name) {
      acc.push({
        label: plan.label,
        value: plan.value,
        children: [
          {
            label:
              "End current subscription and bill + start new subscription with selected plan",
            value: "end_current_subscription_and_bill",
          },
          {
            label:
              "End current subscription and don't bill + start new subscription with selected plan",
            value: "end_current_subscription_dont_bill",
          },
          {
            label: "Switch plan mid-subscription",
            value: "change_subscription_plan",
          },
        ],
      } as PlanOption);
    }
    return acc;
  }, [] as PlanOption[]);

  const onChange = (value: string[], selectedOptions: PlanOption[]) => {
    onPlanChange(subscriptions[0].subscription_id, {
      plan_id: selectedOptions[0].value,
      replace_immediately_type: value[1] as
        | "change_subscription_plan"
        | "end_current_subscription_and_bill"
        | "end_current_subscription_dont_bill",
    });
  };

  const switchMenu = (
    <Cascader
      options={plansWithSwitchOptions}
      onChange={onChange}
      expandTrigger="hover"
      placeholder="Please select"
      showSearch={{ filter }}
      displayRender={displayRender}
      changeOnSelect
    />
  );

  const handleAttachPlanSubmit = () => {
    if (selectedPlan) {
      let plan = idtoPlan[selectedPlan];
      let props: CreateSubscriptionType = {
        customer_id: customer_id,
        plan_id: plan.plan_id,
        start_date: new Date().toISOString(),
        status: "active",
      };
      onCreate(props);
    }
    form.resetFields();
  };

  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center">
        <h3 className="text-xl font-main m-3">No Subscription</h3>
        <p className="font-bold">Please attach a Plan</p>
        <div className=" h-3/6">
          <Form
            onFinish={handleAttachPlanSubmit}
            form={form}
            name="create_subscription"
          >
            <Form.Item name="plan">
              <Select
                showSearch
                placeholder="Select a plan"
                onChange={selectPlan}
                options={planList}
                optionLabelProp="label"
              >
                {" "}
              </Select>
            </Form.Item>
            <Form.Item>
              <Button htmlType="submit">
                {" "}
                Attach Plan and Start Subscription
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    );
  }
  return (
    <div className="mt-auto">
      <h2 className="text-left mb-2">Active Plan</h2>
      <div className="flex flex-col justify-center">
        <List>
          {subscriptions.map((subscription) => (
            <List.Item>
              <Card className=" bg-grey3 w-full">
                <div className="grid grid-cols-3 items-stretch">
                  <h2 className="font-main font-bold">
                    {subscription.billing_plan_name}
                  </h2>
                  <div className="flex flex-col justify-center space-y-3">
                    <p>
                      <b>Subscription ID:</b> {subscription.subscription_id}
                    </p>
                    <p>
                      <b>Start Date:</b>{" "}
                      {dayjs(subscription.start_date).format(
                        "YYYY/MM/DD HH:mm"
                      )}{" "}
                      UTC
                    </p>
                    <p>
                      <b>End Date:</b>{" "}
                      {dayjs(subscription.end_date).format("YYYY/MM/DD HH:mm")}{" "}
                      UTC
                    </p>
                    <p>
                      <b>Renews:</b> {subscription.auto_renew ? "Yes" : "No"}
                    </p>
                  </div>
                </div>
              </Card>
            </List.Item>
          ))}
        </List>
        <div className="grid grid-cols-2 w-full space-x-5 my-6">
          <Dropdown overlay={switchMenu} trigger={["click"]}>
            <Button>Switch Plan</Button>
          </Dropdown>
          <Dropdown overlay={cancelMenu} trigger={["click"]}>
            <Button>Cancel Subscription</Button>
          </Dropdown>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionView;
