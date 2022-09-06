import React, { FC, useState, useEffect } from "react";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { CustomerTableItem } from "../types/customer-type";
import { CustomerType } from "../types/customer-type";
import { Button, Tag } from "antd";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "./LoadingSpinner";
import CreateCustomerForm, { CreateCustomerState } from "./CreateCustomerForm";
import { useMutation } from "react-query";
import { Customer } from "../api/api";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

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
    render: (_, record) => <Tag color={"bruh"}>{record.subscriptions[0]}</Tag>,
  },
  {
    title: "Outstanding Revenue",
    width: 120,
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
};

const CustomerTable: FC<Props> = ({ customerArray }) => {
  const [visible, setVisible] = useState(false);
  const [customerState, setCustomerState] =
    useState<CreateCustomerState>(defaultCustomerState);

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
      <ToastContainer autoClose={1000} />
    </div>
  );
};

export default CustomerTable;
