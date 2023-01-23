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
  Tag,
  Cascader,
} from "antd";
import type { DefaultOptionType } from "antd/es/cascader";
import {
  CreateSubscriptionType,
  TurnSubscriptionAutoRenewOffType,
  ChangeSubscriptionPlanType,
  CancelSubscriptionBody,
  CancelSubscriptionQueryParams,
  SubscriptionType,
} from "../../types/subscription-type";
//import the Customer type from the api.ts file
import dayjs from "dayjs";

import DraftInvoice from "./DraftInvoice";
import { Link } from "react-router-dom";

interface Props {
  customer_id: string;
  subscriptions: SubscriptionType[];
  plans: PlanType[] | undefined;
  onAutoRenewOff: (
    params: object,
    props: TurnSubscriptionAutoRenewOffType
  ) => void;
  onCancel: (
    props: CancelSubscriptionBody,
    params: CancelSubscriptionQueryParams
  ) => void;
  onPlanChange: (params: object, props: ChangeSubscriptionPlanType) => void;
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

  const cancelAndBill = (plan_id, subscription_filters) => {
    const query_params: CancelSubscriptionQueryParams = {
      plan_id: plan_id,
      subscription_filters: subscription_filters,
      customer_id: customer_id,
    };
    const body: CancelSubscriptionBody = {
      usage_behavior: "bill_full",
      flat_fee_behavior: "prorate",
      invoicing_behavior: "invoice_now",
    };
    onCancel(body, query_params);
  };

  const cancelAndDontBill = (plan_id, subscription_filters) => {
    const query_params: CancelSubscriptionQueryParams = {
      plan_id: plan_id,
      subscription_filters: subscription_filters,
      customer_id: customer_id,
    };
    const body: CancelSubscriptionBody = {
      usage_behavior: "bill_none",
      flat_fee_behavior: "prorate",
      invoicing_behavior: "invoice_now",
    };
    onCancel(body, query_params);
  };

  const turnAutoRenewOff = (plan_id, subscription_filters) => {
    onAutoRenewOff(
      {
        plan_id: plan_id,
        subscription_filters: subscription_filters,
        customer_id: customer_id,
      },
      {
        turn_off_auto_renew: true,
      }
    );
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

  const cancelMenu = (plan_id: string, subscription_filters?: object[]) => (
    <Menu
      items={[
        {
          label: (
            <div onClick={() => cancelAndBill(plan_id, subscription_filters)}>
              Cancel and Bill Now
            </div>
          ),
          key: "0",
        },
        // {
        //   label: (
        //     <div
        //       onClick={() => cancelAndDontBill(plan_id, subscription_filters)}
        //     >
        //       Cancel Without Billing & Refund
        //     </div>
        //   ),
        //   key: "1",
        // },
        {
          label: (
            <div
              onClick={() => turnAutoRenewOff(plan_id, subscription_filters)}
            >
              Cancel Renewal
            </div>
          ),
          key: "2",
        },
      ]}
    />
  );

  const plansWithSwitchOptions = (plan_id: string) =>
    planList?.reduce((acc, plan) => {
      if (plan.value !== plan_id) {
        acc.push({
          label: plan.label,
          value: plan.value,
        } as PlanOption);
      }
      return acc;
    }, [] as PlanOption[]);

  const onChange = (
    value: any,
    selectedOptions: PlanOption[],
    plan_id: string,
    subscription_filters: object[]
  ) => {
    onPlanChange(
      {
        plan_id: plan_id,
        customer_id: customer_id,
        subscription_filters: subscription_filters,
      },
      {
        replace_plan_id: selectedOptions[0].value as string,
      }
    );
  };

  const switchMenu = (plan_id: string, subscription_filters: object[]) => (
    <Cascader
      options={plansWithSwitchOptions(plan_id)}
      onChange={(value, selectedOptions) =>
        onChange(value, selectedOptions, plan_id, subscription_filters)
      }
      expandTrigger="hover"
      placeholder="Please select"
      showSearch={{ filter }}
      displayRender={displayRender}
      changeOnSelect
    />
  );

  const handleAttachPlanSubmit = () => {
    if (selectedPlan) {
      const plan = idtoPlan[selectedPlan];
      const props: CreateSubscriptionType = {
        customer_id: customer_id,
        plan_id: plan.plan_id,
        start_date: new Date().toISOString(),
        auto_renew: true,
        is_new: true,
        subscription_filters: [],
      };
      onCreate(props);
    }
    form.resetFields();
  };
  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center">
        <h2 className="mb-2 pb-4 pt-4 font-bold text-main">No Subscription</h2>
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
      <h2 className="mb-2 pb-4 pt-4 font-bold text-main">Active Plans</h2>
      <div className="flex flex-col justify-center">
        <List>
          {subscriptions.map((subPlan) => (
            <Fragment key={subPlan.billing_plan.plan_id}>
              <List.Item>
                <Card className=" bg-grey3 w-full">
                  <div className="grid grid-cols-2 items-stretch">
                    <div>
                      <Link to={"../plans/" + subPlan.billing_plan.plan_id}>
                        {" "}
                        <h2 className="font-main font-bold hover:underline">
                          {subPlan.billing_plan.plan_name}
                        </h2>
                      </Link>
                      <b>Subscription Filters: </b>{" "}
                      {subPlan.subscription_filters &&
                      subPlan.subscription_filters.length > 0
                        ? subPlan.subscription_filters?.map((filter) => (
                            <div>
                              {filter["property_name"]}: {filter["value"]}
                            </div>
                          ))
                        : "None"}
                    </div>

                    <div className="grid grid-cols-2 justify-center space-y-3">
                      <p className=""></p>
                      <p>
                        <b>Start Date:</b>{" "}
                        {dayjs(subPlan.start_date).format("YYYY/MM/DD HH:mm")}{" "}
                      </p>

                      <p>
                        <b>Renews:</b>{" "}
                        {subPlan.auto_renew ? (
                          <Tag color="green">Yes</Tag>
                        ) : (
                          <Tag color="red">No</Tag>
                        )}
                      </p>
                      <p>
                        <b>End Date:</b>{" "}
                        {dayjs(subPlan.end_date).format("YYYY/MM/DD HH:mm")}{" "}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 w-full space-x-5 mt-12">
                    <Dropdown
                      overlay={switchMenu(
                        subPlan.billing_plan.plan_id,
                        subPlan.subscription_filters
                      )}
                      trigger={["click"]}
                      className="w-6/12 justify-self-center"
                    >
                      <Button>Switch Plan</Button>
                    </Dropdown>
                    <Dropdown
                      overlay={cancelMenu(
                        subPlan.billing_plan.plan_id,
                        subPlan.subscription_filters
                      )}
                      trigger={["click"]}
                      className="w-6/12 justify-self-center"
                    >
                      <Button>Cancel Subscriptions</Button>
                    </Dropdown>
                  </div>
                </Card>
              </List.Item>
            </Fragment>
          ))}
        </List>

        <DraftInvoice customer_id={customer_id} />
      </div>
    </div>
  );
};

export default SubscriptionView;
