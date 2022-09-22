import React, { FC, useState, useEffect } from "react";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { CustomerTableItem } from "../../types/customer-type";
import { CustomerType } from "../../types/customer-type";
import { Button, Tag } from "antd";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "../LoadingSpinner";
import CreateCustomerForm, { CreateCustomerState } from "../CreateCustomerForm";
import { useMutation, useQuery, UseQueryResult } from "react-query";
import { Customer, Plan } from "../../api/api";
import { PlanType } from "../../types/plan-type";
import { CreateSubscriptionType } from "../../types/subscription-type";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import CustomerDetail from "./CustomerDetail";

const columns: ProColumns<CustomerTableItem>[] = [
  {
    title: "Customer Id",
    width: 120,
    dataIndex: "customer_id",
    align: "left",
  },
  {
    title: "Name",
    width: 120,
    dataIndex: "customer_name",
    align: "left",
  },
  {
    title: "Plans",
    width: 120,
    dataIndex: "subscriptions",
    render: (_, record) => (
      <Tag color={"default"}>{record.subscriptions[0]}</Tag>
    ),
  },
  {
    title: "Outstanding Revenue",
    width: 120,
    render: (_, record) => <p>${record.total_revenue_due}</p>,
    dataIndex: "total_revenue_due",
  },
];

interface Props {
  customerArray: CustomerTableItem[];
}

const defaultCustomerState: CreateCustomerState = {
  title: "Create a Customer",
  name: "",
  customer_id: "",
  subscriptions: [],
};

const CustomerTable: FC<Props> = ({ customerArray }) => {
  const [visible, setVisible] = useState(false);
  const [customerVisible, setCustomerVisible] = useState(false);
  const [customerState, setCustomerState] =
    useState<CreateCustomerState>(defaultCustomerState);

  const { data, isLoading }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(
    ["plans"],
    () =>
      Plan.getPlans().then((res) => {
        return res;
      })
  );

  const mutation = useMutation(
    (post: CustomerType) => Customer.createCustomer(post),
    {
      onSuccess: () => {
        setVisible(false);
        toast.success("Customer created successfully", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const subscribe = useMutation((post: CreateSubscriptionType) =>
    Customer.subscribe(post)
  );

  const onDetailCancel = () => {
    setCustomerVisible(false);
  };

  const changePlan = (plan_id: string, customer_id: string) => {
    console.log(plan_id, customer_id);
  };

  const rowModal = (record: any) => {
    setCustomerVisible(true);
    setCustomerState({
      title: "Customer Detail",
      name: record.customer_name,
      customer_id: record.customer_id,
      subscriptions: record.subscriptions,
    });
  };
  const openCustomerModal = () => {
    setVisible(true);
    setCustomerState(defaultCustomerState);
  };

  const onCancel = () => {
    setVisible(false);
  };

  const onSave = (state: CreateCustomerState) => {
    const customerInstance: CustomerType = {
      customer_id: state.customer_id,
      name: state.name,
    };
    mutation.mutate(customerInstance);
  };
  return (
    <div>
      <ProTable<CustomerTableItem>
        columns={columns}
        dataSource={customerArray}
        rowKey="customer_id"
        onRow={(record, rowIndex) => {
          return {
            onClick: (event) => {
              rowModal(record);
            }, // click row
          };
        }}
        search={false}
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
        }}
        options={false}
        toolBarRender={() => [
          <Button
            type="primary"
            className="ml-auto bg-info"
            onClick={openCustomerModal}
          >
            Create Customer
          </Button>,
        ]}
      />
      <CreateCustomerForm
        state={customerState}
        visible={visible}
        onSave={onSave}
        onCancel={onCancel}
      />
      <CustomerDetail
        key={customerState.customer_id}
        visible={customerVisible}
        onCancel={onDetailCancel}
        changePlan={changePlan}
        plans={data}
        customer={customerState}
      />
      <ToastContainer autoClose={1000} />
    </div>
  );
};

export default CustomerTable;
