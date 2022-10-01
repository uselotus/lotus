import React, { useState } from "react";
import { Form, Tabs, Modal, Select } from "antd";
import { PlanType } from "../../types/plan-type";
import { CreateSubscriptionType } from "../../types/subscription-type";
import LoadingSpinner from "../LoadingSpinner";
import { Customer } from "../../api/api";
import SubscriptionView, {
  cancelSubscriptionType,
} from "./CustomerSubscriptionView";
import {
  useMutation,
  useQueryClient,
  useQuery,
  UseQueryResult,
} from "react-query";
import dayjs from "dayjs";
import {
  CustomerDetailType,
  CustomerDetailSubscription,
} from "../../types/customer-type";
import "./CustomerDetail.css";

const { Option } = Select;

function CustomerDetail(props: {
  visible: boolean;
  onCancel: () => void;
  customer_id: string;
  plans: PlanType[] | undefined;
  changePlan: (plan_id: string, customer_id: string) => void;
}) {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const [currentTab, setCurrentTab] = useState("subscriptions");
  const [customerSubscriptions, setCustomerSubscriptions] = useState<
    CustomerDetailSubscription[]
  >([]);

  const { data, isLoading }: UseQueryResult<CustomerDetailType> =
    useQuery<CustomerDetailType>(["customer_detail", props.customer_id], () =>
      Customer.getCustomerDetail(props.customer_id).then((res) => {
        setCustomerSubscriptions(res.subscriptions);
        return res;
      })
    );

  const mutation = useMutation(
    (post: CreateSubscriptionType) => Customer.subscribe(post),
    {
      onSettled: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", props.customer_id]);
      },
    }
  );

  const cancelMutation = useMutation(
    (post: cancelSubscriptionType) => Customer.cancelSubscription(post),
    {
      onSettled: () => {
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_detail", props.customer_id]);
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
      customer_id: props.customer_id,
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
        <div className="flex justify-between flex-col max-w">
          <div className="text-left	">
            <h2 className="text-2xl font-main mb-3">{data?.customer_name}</h2>
            <p>Id: {props.customer_id}</p>
          </div>
          <div className="flex items-center flex-col">
            <Tabs
              onChange={onClick}
              defaultActiveKey="subscriptions"
              centered
              activeKey={currentTab}
              className="w-full"
            >
              {" "}
              <Tabs.TabPane disabled={false} tab="Detail" key="detail">
                {data !== undefined ? (
                  <div className="grid grid-cols-2">
                    <div className=" space-y-3">
                      <h2>Info</h2>
                      <p>Email: {data.email}</p>
                      <p>Billing Address: {data.billing_address}</p>
                    </div>
                    <div className="space-y-3">
                      <h2>Timeline</h2>
                    </div>
                  </div>
                ) : (
                  <h2> No Data </h2>
                )}
              </Tabs.TabPane>
              <Tabs.TabPane tab="Subscriptions" key="subscriptions">
                {data !== undefined ? (
                  <div key={props.customer_id}>
                    <SubscriptionView
                      key={props.customer_id}
                      subscriptions={data?.subscriptions}
                      plans={props.plans}
                      onChange={addSubscriptions}
                      onCancel={cancelSubscription}
                    />
                  </div>
                ) : null}
              </Tabs.TabPane>
              <Tabs.TabPane disabled={true} tab="Invoices" key="invoices">
                <p>Invoices</p>
              </Tabs.TabPane>{" "}
            </Tabs>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default CustomerDetail;
