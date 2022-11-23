import React, { useState } from "react";
import { Form, Tabs, Modal } from "antd";
import { PlanType } from "../../types/plan-type";
import { Card, Col, Row, Select } from "antd";
import {
  CreateSubscriptionType,
  TurnSubscriptionAutoRenewOffType,
  ChangeSubscriptionPlanType,
  CancelSubscriptionType,
} from "../../types/subscription-type";
import LoadingSpinner from "../LoadingSpinner";
import { Customer } from "../../api/api";
import SubscriptionView from "./CustomerSubscriptionView";
import {
  useMutation,
  useQueryClient,
  useQuery,
  UseQueryResult,
} from "react-query";
import {
  CustomerDetailType,
  CustomerDetailSubscription,
} from "../../types/customer-type";
import "./CustomerDetail.css";
import CustomerInvoiceView from "./CustomerInvoices";
import CustomerBalancedAdjustments from "./CustomerBalancedAdjustments";
import { CustomerIntegrations } from "./CustomerIntegrations";
import { CustomerCostType } from "../../types/revenue-type";
import CustomerInfoView from "./CustomerInfo";
import dayjs from "dayjs";
import { toast } from "react-toastify";

const { Option } = Select;

const dummyData = {
  stripe: {
    key: "stripe_dummy_key",
    account_type: "stripe_dummy_account",
    name: "dummy name",
    email: "abc@dummy.com",
  },
  paypal: {
    key: "stripe_dummy_key",
    account_type: "stripe_dummy_account",
    name: "dummy name",
    email: "abc@dummy.com",
  },
};

function CustomerDetail(props: {
  visible: boolean;
  onCancel: () => void;
  customer_id: string;
  plans: PlanType[] | undefined;
  changePlan: (plan_id: string, customer_id: string) => void;
}) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState<string>(
    dayjs().subtract(1, "month").format("YYYY-MM-DD")
  );
  const [endDate, setEndDate] = useState<string>(dayjs().format("YYYY-MM-DD"));

  const [customerSubscriptions, setCustomerSubscriptions] = useState<
    CustomerDetailSubscription[]
  >([]);

  const { data, isLoading }: UseQueryResult<CustomerDetailType> =
    useQuery<CustomerDetailType>(
      ["customer_detail", props.customer_id],
      () =>
        Customer.getCustomerDetail(props.customer_id).then((res) => {
          setCustomerSubscriptions(res.subscriptions);
          return res;
        }),
      {
        enabled: props.visible,
      }
    );

  const { data: cost_analysis, isLoading: cost_analysis_loading } =
    useQuery<CustomerCostType>(
      ["customer_cost_analysis", props.customer_id, startDate, endDate],
      () => Customer.getCost(props.customer_id, startDate, endDate),
      {
        enabled: props.visible,
        placeholderData: {
          per_day: [],
          total_revenue: 0,
          total_cost: 0,
          margin: 0,
        },
      }
    );

  const createSubscriptionMutation = useMutation(
    (post: CreateSubscriptionType) => Customer.createSubscription(post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", props.customer_id]);
        toast.success("Subscription created successfully");
      },
    }
  );

  const cancelSubscriptionMutation = useMutation(
    (obj: { subscription_id: string; post: CancelSubscriptionType }) =>
      Customer.cancelSubscription(obj.subscription_id, obj.post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", props.customer_id]);
        toast.success("Subscription cancelled successfully");
      },
    }
  );

  const changeSubscriptionPlanMutation = useMutation(
    (obj: { subscription_id: string; post: ChangeSubscriptionPlanType }) =>
      Customer.changeSubscriptionPlan(obj.subscription_id, obj.post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", props.customer_id]);
        toast.success("Subscription switched successfully");
      },
    }
  );

  const turnSubscriptionAutoRenewOffMutation = useMutation(
    (obj: {
      subscription_id: string;
      post: TurnSubscriptionAutoRenewOffType;
    }) => Customer.turnSubscriptionAutoRenewOff(obj.subscription_id, obj.post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", props.customer_id]);
        toast.success("Subscription auto renew turned off");
      },
    }
  );

  const cancelSubscription = (
    subscription_id: string,
    props: CancelSubscriptionType
  ) => {
    cancelSubscriptionMutation.mutate({
      subscription_id: subscription_id,
      post: props,
    });
  };

  const changeSubscriptionPlan = (
    subscription_id: string,
    props: ChangeSubscriptionPlanType
  ) => {
    changeSubscriptionPlanMutation.mutate({
      subscription_id: subscription_id,
      post: props,
    });
  };

  const turnSubscriptionAutoRenewOff = (
    subscription_id: string,
    props: TurnSubscriptionAutoRenewOffType
  ) => {
    turnSubscriptionAutoRenewOffMutation.mutate({
      subscription_id: subscription_id,
      post: props,
    });
  };

  const refetchGraphData = (start_date: string, end_date: string) => {
    setStartDate(start_date);
    setEndDate(end_date);
    queryClient.invalidateQueries([
      "customer_cost_analysis",
      props.customer_id,
    ]);
  };

  const createSubscription = (props: CreateSubscriptionType) => {
    createSubscriptionMutation.mutate(props);
  };

  return (
    <Modal
      visible={props.visible}
      title={"Customer Detail"}
      onCancel={props.onCancel}
      okType="default"
      onOk={props.onCancel}
      footer={null}
      width={1000}
    >
      {props.plans === undefined ? (
        <div>
          <LoadingSpinner />
        </div>
      ) : (
        <div className="flex justify-between flex-col max-w mx-3">
          <div className="text-left	">
            <h1 className="mb-4">{data?.customer_name}</h1>
            <div className="flex flex-row">
              <div className="plansDetailLabel">ID:&nbsp; </div>
              <div className="plansDetailValue">{props.customer_id}</div>
            </div>
          </div>
          <div
            className="flex items-center flex-col mt-6"
            onClick={(e) => e.stopPropagation()}
          >
            <Tabs defaultActiveKey="subscriptions" centered className="w-full">
              <Tabs.TabPane tab="Detail" key="detail">
                {data !== undefined && cost_analysis !== undefined ? (
                  <CustomerInfoView
                    data={data}
                    cost_data={cost_analysis}
                    onDateChange={refetchGraphData}
                  />
                ) : (
                  <h2> No Data </h2>
                )}
              </Tabs.TabPane>
              <Tabs.TabPane tab="Subscriptions" key="subscriptions">
                {data !== undefined ? (
                  <div key={props.customer_id}>
                    <SubscriptionView
                      customer_id={props.customer_id}
                      subscriptions={data?.subscriptions}
                      plans={props.plans}
                      onCreate={createSubscription}
                      onCancel={cancelSubscription}
                      onPlanChange={changeSubscriptionPlan}
                      onAutoRenewOff={turnSubscriptionAutoRenewOff}
                    />
                  </div>
                ) : null}
              </Tabs.TabPane>
              <Tabs.TabPane tab="Invoices" key="invoices">
                <CustomerInvoiceView invoices={data?.invoices} />
              </Tabs.TabPane>
              <Tabs.TabPane tab="Credits" key="credits">
                <CustomerBalancedAdjustments
                  balanceAdjustments={data?.balance_adjustments}
                />
              </Tabs.TabPane>
              <Tabs.TabPane tab="Integrations" key="integrations">
                {data?.integrations ? (
                  <CustomerIntegrations integrations={data?.integrations} />
                ) : (
                  <h2> No Integrations </h2>
                )}
              </Tabs.TabPane>{" "}
            </Tabs>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default CustomerDetail;
