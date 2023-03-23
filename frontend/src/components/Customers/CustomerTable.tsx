// @ts-ignore
import React, { FC, useState, useEffect } from "react";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { Button, Input, Tag } from "antd";
import { useQuery, UseQueryResult, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from "react-router-dom";
import {
  CustomerSummary,
  CustomerTableItem,
  CustomerTotal,
} from "../../types/customer-type";
import { CreateCustomerState } from "./CreateCustomerForm";
import { Plan } from "../../api/api";
import { PlanType } from "../../types/plan-type";
import CustomerDetail from "./CustomerDetail";

function getHighlightedText(text: string, highlight: string) {
  // Split text on highlight term, include term itself into parts, ignore case
  if (text) {
    const parts = text.split(new RegExp(`(${highlight})`, "gi"));
    return (
      <span>
        {parts.map((part) =>
          part.toLowerCase() === highlight.toLowerCase() ? (
            <span className="highlightText">{part}</span>
          ) : (
            part
          )
        )}
      </span>
    );
  }
}

interface Props {
  customerArray: CustomerSummary[];
  totals: CustomerTotal[] | undefined;
}

const defaultCustomerState: CreateCustomerState = {
  title: "Create a Customer",
  name: "",
  customer_id: "",
  subscriptions: [],
  total_amount_due: 0,
  email: "",
};

const CustomerTable: FC<Props> = ({ customerArray, totals }) => {
  const [customerVisible, setCustomerVisible] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [customerState, setCustomerState] =
    useState<CreateCustomerState>(defaultCustomerState);
  const [tableData, setTableData] = useState<CustomerTableItem[]>();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    if (customerArray !== undefined) {
      const dataInstance: CustomerTableItem[] = [];
      if (totals !== undefined) {
        for (let i = 0; i < customerArray.length; i++) {
          const customer_info = customerArray[i];
          const total =
            totals.find(
              (total) => total.customer_id === customer_info.customer_id
            )?.total_amount_due ?? 0.0;
          const entry: CustomerTableItem = {
            ...customer_info,
            total_amount_due: total,
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
    }
  }, [customerArray, totals]);

  const { data, isLoading }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(
    ["plan_list"],
    () => Plan.getPlans().then((res) => res)
  );

  const columns: ProColumns<CustomerTableItem>[] = [
    {
      width: 10,
    },
    {
      title: "Customer ID",
      width: 120,
      dataIndex: "customer_id",
      align: "left",
      ellipsis: true,
      render: (_, record) => {
        if (searchQuery) {
          return getHighlightedText(record.customer_id, searchQuery);
        }
        return record.customer_id;
      },
    },
    {
      title: "Name",
      width: 120,
      dataIndex: "customer_name",
      align: "left",
      search: { transform: (value: any) => value },
      render: (_, record) => {
        if (searchQuery) {
          getHighlightedText(record.customer_name, searchQuery);
        }
        return record.customer_name;
      },
    },
    {
      title: "Plans",
      width: 180,
      dataIndex: "subscriptions",
      render: (_, record) => (
        <div>
          {record.subscriptions.length < 3 &&
            record.subscriptions.map((sub, index) => (
              <div>
                <Tag color="default">{sub.billing_plan_name}</Tag>
                <Tag color="default">v{sub.plan_version}</Tag>{" "}
              </div>
            ))}
          {record.subscriptions.length >= 3 && (
            <div>
              <div>
                <Tag color="default">
                  {record.subscriptions[0].billing_plan_name}
                </Tag>
                <Tag color="default">
                  v{record.subscriptions[0].plan_version}
                </Tag>{" "}
              </div>
              <div>
                <Tag color="default">
                  {record.subscriptions[1].billing_plan_name}
                </Tag>
                <Tag color="default">
                  v{record.subscriptions[1].plan_version}
                </Tag>{" "}
              </div>
              {"..."}
            </div>
          )}
        </div>
      ),
    },
    {
      title: (
        <div>
          Oustanding <br /> Revenue
        </div>
      ),
      width: 60,
      sorter: (a, b) => a.total_amount_due - b.total_amount_due,

      render: (_, record) => (
        <div className="self-center">
          {record.total_amount_due !== undefined &&
          record.total_amount_due !== null ? (
            <div>${record.total_amount_due.toFixed(2)}</div>
          ) : (
            <div>${0.0}</div>
          )}
        </div>
      ),
      dataIndex: "total_amount_due",
    },
    {
      title: (
        <div>
          Subscription <br /> Renews
        </div>
      ),
      width: 60,
      render: (_, record) => (
        <div>
          {record.subscriptions[0] !== undefined &&
            (record.subscriptions[0].auto_renew ? (
              <Tag color="green">Renews</Tag>
            ) : (
              <Tag color="red">Ends</Tag>
            ))}
        </div>
      ),
      dataIndex: "auto_renew",
    },
  ];

  const onDetailCancel = () => {
    queryClient.invalidateQueries(["customer_list"]);
    queryClient.invalidateQueries(["customer_totals"]);
    queryClient.invalidateQueries([
      "customer_detail",
      customerState.customer_id,
    ]);

    setCustomerVisible(false);
  };

  const changePlan = (plan_id: string, customer_id: string) => {};

  const getFilteredTableData = (data: CustomerTableItem[] | undefined) => {
    if (data === undefined) {
      return data;
    }
    if (!searchQuery) {
      return data;
    }
    return data.filter(
      (item) =>
        item.customer_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (item.customer_name &&
          item.customer_name.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  };

  return (
    <>
      <Input
        className="customer-search"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Search Customer"
      />
      <div className="border-2 border-solid rounded border-[#EAEAEB]">
        <ProTable
          columns={columns}
          dataSource={getFilteredTableData(tableData)}
          rowKey="customer_id"
          onRow={(record) => ({
            onClick: () => navigate(`/customers/${record.customer_id}`), // click row
          })}
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
      </div>
    </>
  );
};

export default CustomerTable;
