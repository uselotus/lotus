import React, { useState } from "react";
import { Form, Tabs, Modal, Button } from "antd";
import {
  useMutation,
  useQueryClient,
  useQuery,
  UseQueryResult,
} from "react-query";
import dayjs from "dayjs";
import { toast } from "react-toastify";
import { useNavigate, useParams } from "react-router-dom";
import { PlanType } from "../../types/plan-type";
import {
  CreateSubscriptionType,
  TurnSubscriptionAutoRenewOffType,
  ChangeSubscriptionPlanType,
  CancelSubscriptionBody,
  CancelSubscriptionQueryParams,
} from "../../types/subscription-type";
import LoadingSpinner from "../LoadingSpinner";
import { Customer, Plan, PricingUnits } from "../../api/api";
import SubscriptionView from "./CustomerSubscriptionView";
import { CustomerType, DetailPlan } from "../../types/customer-type";
import "./CustomerDetail.css";
import CustomerInvoiceView from "./CustomerInvoices";
import CustomerBalancedAdjustments from "./CustomerBalancedAdjustments";
import { CustomerCostType } from "../../types/revenue-type";
import CustomerInfoView from "./CustomerInfo";

import CopyText from "../base/CopytoClipboard";
import { CurrencyType } from "../../types/pricing-unit-type";
import { PageLayout } from "../base/PageLayout";

type CustomerDetailsParams = {
  customerId: string;
};
function CustomerDetail() {
  const { customerId: customer_id } = useParams<CustomerDetailsParams>();
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState<string>(
    dayjs().subtract(1, "month").format("YYYY-MM-DD")
  );
  const [endDate, setEndDate] = useState<string>(dayjs().format("YYYY-MM-DD"));
  const { data: plans }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(
    ["plan_list"],
    () => Plan.getPlans().then((res) => res)
  );

  const { data: pricingUnits }: UseQueryResult<CurrencyType[]> = useQuery<
    CurrencyType[]
  >(["pricing_unit_list"], () => PricingUnits.list().then((res) => res));
  const { data, isLoading, refetch }: UseQueryResult<CustomerType> =
    useQuery<CustomerType>(["customer_detail", customer_id], () =>
      Customer.getCustomerDetail(customer_id as string).then((res) => res)
    );

  const { data: cost_analysis, isLoading: cost_analysis_loading } =
    useQuery<CustomerCostType>(
      ["customer_cost_analysis", customer_id, startDate, endDate],
      () => Customer.getCost(customer_id as string, startDate, endDate),
      {
        enabled: true,
        placeholderData: {
          per_day: [],
          total_revenue: 0,
          total_cost: 0,
          margin: 0,
        },
      }
    );
  console.log(data);
  const createSubscriptionMutation = useMutation(
    (post: CreateSubscriptionType) => Customer.createSubscription(post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", customer_id]);
        queryClient.invalidateQueries(["balance_adjustments", customer_id]);
        queryClient.invalidateQueries(["draft_invoice", customer_id]);
        refetch();
        toast.success("Subscription created successfully");
      },
    }
  );

  const cancelSubscriptionMutation = useMutation(
    (obj: {
      post: CancelSubscriptionBody;
      params: CancelSubscriptionQueryParams;
    }) => Customer.cancelSubscription(obj.params, obj.post),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries([
          "balance_adjustments",
          props.customer_id,
        ]);
        queryClient.invalidateQueries(["draft_invoice", props.customer_id]);
        refetch();
        toast.success("Subscription cancelled successfully");
      },
    }
  );

  const changeSubscriptionPlanMutation = useMutation(
    (obj: { params: object; post: ChangeSubscriptionPlanType }) =>
      Customer.changeSubscriptionPlan(obj.post, obj.params),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries([
          "balance_adjustments",
          props.customer_id,
        ]);
        queryClient.invalidateQueries(["draft_invoice", props.customer_id]);
        refetch();
        toast.success("Subscription switched successfully");
      },
    }
  );

  const turnSubscriptionAutoRenewOffMutation = useMutation(
    (obj: { params: object; post: TurnSubscriptionAutoRenewOffType }) =>
      Customer.turnSubscriptionAutoRenewOff(obj.post, obj.params),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["customer_list"]);
        refetch();
        toast.success("Subscription auto renew turned off");
      },
    }
  );

  const cancelSubscription = (
    props: CancelSubscriptionBody,
    params: CancelSubscriptionQueryParams
  ) => {
    cancelSubscriptionMutation.mutate({
      post: props,
      params,
    });
  };

  const changeSubscriptionPlan = (
    params: object,
    props: ChangeSubscriptionPlanType
  ) => {
    changeSubscriptionPlanMutation.mutate({
      params,
      post: props,
    });
  };

  const turnSubscriptionAutoRenewOff = (
    params: object,
    props: TurnSubscriptionAutoRenewOffType
  ) => {
    turnSubscriptionAutoRenewOffMutation.mutate({
      params,
      post: props,
    });
  };

  const refetchGraphData = (start_date: string, end_date: string) => {
    setStartDate(start_date);
    setEndDate(end_date);
    queryClient.invalidateQueries(["customer_cost_analysis", customer_id]);
  };

  const createSubscription = (props: CreateSubscriptionType) => {
    createSubscriptionMutation.mutate(props);
  };

  return (
    <PageLayout
      title={data?.customer_name}
      className="text-[24px] font-alliance "
      hasBackButton
      aboveTitle
      backButton={
        <div>
          <Button
            onClick={() => navigate(-1)}
            type="primary"
            size="large"
            key="create-custom-plan"
            style={{
              background: "#F5F5F5",
              borderColor: "#F5F5F5",
            }}
          >
            <div className="flex items-center justify-between text-black">
              <div>&larr; Go back</div>
            </div>
          </Button>
        </div>
      }
    >
      {plans === undefined ? (
        <div className="min-h-[60%]">
          <LoadingSpinner />
        </div>
      ) : (
        <Tabs defaultActiveKey="details" size="large">
          <Tabs.TabPane tab="Details" key="details">
            {data !== undefined &&
            cost_analysis !== undefined &&
            pricingUnits !== undefined ? (
              <CustomerInfoView
                data={data}
                cost_data={cost_analysis}
                refetch={refetch}
                pricingUnits={pricingUnits}
                onDateChange={refetchGraphData}
              />
            ) : (
              <div className="min-h-[60%]">
                <LoadingSpinner />
              </div>
            )}
          </Tabs.TabPane>
          <Tabs.TabPane tab="Subscriptions" key="subscriptions">
            {data !== undefined ? (
              <div key={customer_id}>
                <SubscriptionView
                  customer_id={customer_id as string}
                  subscriptions={data.subscriptions}
                  plans={plans}
                  onCreate={createSubscription}
                  onCancel={cancelSubscription}
                  onPlanChange={changeSubscriptionPlan}
                  onAutoRenewOff={turnSubscriptionAutoRenewOff}
                />
              </div>
            ) : (
              <div className="h-192" />
            )}
          </Tabs.TabPane>
          <Tabs.TabPane tab="Invoices" key="invoices">
            <CustomerInvoiceView invoices={data?.invoices} />
          </Tabs.TabPane>
          <Tabs.TabPane tab="Credits" key="credits">
            <CustomerBalancedAdjustments customerId={customer_id as string} />
          </Tabs.TabPane>
        </Tabs>
      )}
    </PageLayout>
  );
}

export default CustomerDetail;
