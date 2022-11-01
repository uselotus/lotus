import React, { FC, useState, useEffect } from "react";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import {
  CustomerPlus,
  CustomerTableItem,
  CustomerTotal,
  CustomerDetailSubscription,
} from "../../types/customer-type";
import { Button, Tag } from "antd";
import LoadingSpinner from "../LoadingSpinner";
import CreateCustomerForm, { CreateCustomerState } from "./CreateCustomerForm";
import {
  useMutation,
  useQuery,
  UseQueryResult,
  useQueryClient,
} from "react-query";
import { Customer, Plan } from "../../api/api";
import { PlanType } from "../../types/plan-type";
import { CreateSubscriptionType } from "../../types/subscription-type";
import { toast } from "react-toastify";
import CustomerDetail from "./CustomerDetail";

const columns: ProColumns<CustomerTableItem>[] = [
  {
    title: "Customer ID",
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
      <div>
        {record.subscriptions.map((sub) => (
          <div>
            <Tag color={"default"}>{sub.billing_plan_name}</Tag>
            <Tag color={"default"}>v{sub.plan_version}</Tag>{" "}
          </div>
        ))}
      </div>
    ),
  },
  {
    title: "Outstanding Revenue",
    width: 120,
    render: (_, record) => (
      <div>
        {record.total_amount_due !== undefined ? (
          <p>${record.total_amount_due.toFixed(2)}</p>
        ) : (
          <p>${0.0}</p>
        )}
      </div>
    ),
    dataIndex: "total_amount_due",
  },
];

interface Props {
  customerArray: CustomerPlus[];
  totals: CustomerTotal[] | undefined;
}

const defaultCustomerState: CreateCustomerState = {
  title: "Create a Customer",
  name: "",
  customer_id: "",
  subscriptions: [],
  total_amount_due: 0,
};

const CustomerTable: FC<Props> = ({ customerArray, totals }) => {
  const [customerVisible, setCustomerVisible] = useState(false);
  const [customerState, setCustomerState] =
    useState<CreateCustomerState>(defaultCustomerState);
  const [tableData, setTableData] = useState<CustomerTableItem[]>();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (customerArray !== undefined) {
      const dataInstance: CustomerTableItem[] = [];
      if (totals !== undefined) {
        for (let i = 0; i < customerArray.length; i++) {
          const entry: CustomerTableItem = {
            ...customerArray[i],
            ...totals[i],
          };
          dataInstance.push(entry);
        }
      } else {
        for (let i = 0; i < customerArray.length; i++) {
          const entry: CustomerTableItem = {
            ...customerArray[i],
            total_amount_due: 0.0,
          };
          dataInstance.push(entry);
        }
      }
      setTableData(dataInstance);
      console.log(dataInstance);
    }
  }, [customerArray, totals]);

  const { data, isLoading }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(
    ["plans"],
    () =>
      Plan.getPlans().then((res) => {
        return res;
      })
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
      total_amount_due: record.total_amount_due,
    });
  };

  return (
    <div className="border-solid rounded border-[#EAEAEB]">
      <ProTable
        columns={columns}
        dataSource={tableData}
        rowKey="customer_id"
        onRow={(record, rowIndex) => {
          return {
            onClick: (event) => {
              rowModal(record);
            }, // click row
          };
        }}
        toolBarRender={false}
        search={false}
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
          pageSize: 10,
        }}
        options={false}
      />

      <CustomerDetail
        key={customerState.customer_id}
        visible={customerVisible}
        onCancel={onDetailCancel}
        changePlan={changePlan}
        plans={data}
        customer_id={customerState.customer_id}
      />
    </div>
  );
};

export default CustomerTable;
