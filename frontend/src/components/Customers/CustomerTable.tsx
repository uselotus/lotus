// @ts-ignore
import React, { FC, useState, useEffect } from "react";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import {
  CustomerPlus,
  CustomerTableItem,
  CustomerTotal,
} from "../../types/customer-type";
import {Button, Input, Tag} from "antd";
import { CreateCustomerState } from "./CreateCustomerForm";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { Plan } from "../../api/api";
import { PlanType } from "../../types/plan-type";
import CustomerDetail from "./CustomerDetail";
import { useNavigate } from "react-router-dom";

function getHighlightedText(text:string, highlight:string) {
    // Split text on highlight term, include term itself into parts, ignore case
    const parts = text.split(new RegExp(`(${highlight})`, 'gi'));
    return <span>{parts.map(part => part.toLowerCase() === highlight.toLowerCase() ? <span className="highlightText">{part}</span> : part)}</span>;
}

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
    }
  }, [customerArray, totals]);

  const { data, isLoading }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(
    ["plan_list"],
    () =>
      Plan.getPlans().then((res) => {
        return res;
      })
  );

  const columns: ProColumns<CustomerTableItem>[] = [
  {
    title: "Customer ID",
    width: 120,
    dataIndex: "customer_id",
    align: "left",
    ellipsis: true,
    render: (_, record) => {
        if(searchQuery) {
            return getHighlightedText(record.customer_id, searchQuery)
        }
        return record.customer_id
    }
  },
  {
    title: "Name",
    width: 120,
    dataIndex: "customer_name",
    align: "left",
    search: { transform: (value: any) => value },
    render: (_, record) => {
          if (searchQuery) {
              return getHighlightedText(record.customer_name, searchQuery)
          }
          return record.customer_name
    }
  },
  {
    title: "Plans",
    width: 180,
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
    width: 60,
    sorter: (a, b) => a.total_amount_due - b.total_amount_due,

    render: (_, record) => (
      <div className="self-center">
        {record.total_amount_due !== undefined ? (
          <div>${record.total_amount_due.toFixed(2)}</div>
        ) : (
          <div>${0.0}</div>
        )}
      </div>
    ),
    dataIndex: "total_amount_due",
  },
  {
    title: "Subscription Renews",
    width: 60,
    render: (_, record) => (
      <div>
        {record.subscriptions[0] !== undefined &&
          (record.subscriptions[0].auto_renew ? (
            <Tag color={"green"}>Renews</Tag>
          ) : (
            <Tag color={"red"}>Ends</Tag>
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

  const rowModal = (record: any) => {
    setCustomerVisible(true);
    setCustomerState({
      title: "Customer Detail",
      name: record.customer_name,
      customer_id: record.customer_id,
      subscriptions: record.subscriptions,
      total_amount_due: record.total_amount_due,
      email: record.email,
    });
  };

  const getFilteredTableData = (data: CustomerTableItem[]) => {
      if(!searchQuery) {
          return data
      }
      return data.filter(item =>
          item.customer_id.toLowerCase().includes(searchQuery.toLowerCase())
          || item.customer_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
  }

  return (
  <>
    <Input className="customer-search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
           placeholder="Search Customer"/>
    <div className="border-2 border-solid rounded border-[#EAEAEB]">

      <ProTable
        columns={columns}
        dataSource={getFilteredTableData(tableData)}
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

      {customerVisible && (
        <CustomerDetail
          key={customerState.customer_id}
          visible={customerVisible}
          onCancel={onDetailCancel}
          changePlan={changePlan}
          plans={data}
          customer_id={customerState.customer_id}
        />
      )}
    </div>
   </>
  );
};

export default CustomerTable;
