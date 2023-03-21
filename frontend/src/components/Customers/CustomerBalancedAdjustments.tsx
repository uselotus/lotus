import { Table, Button, Select, Dropdown, Menu, Tag } from "antd";
import React, { FC, useState, useEffect } from "react";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
  UseQueryResult,
} from "@tanstack/react-query";
import { MoreOutlined } from "@ant-design/icons";
import { toast } from "react-toastify";
import { ColumnsType } from "antd/es/table";
import { Credits } from "../../api/api";
import PricingUnitDropDown from "../PricingUnitDropDown";
import { CreditType, DrawdownType } from "../../types/balance-adjustment";
import CreateCredit from "../../pages/CreateBalanceAdjustment";

interface Props {
  customerId: string;
}

const views = ["grouped", "chronological"];
const defaultView = "grouped";

const CustomerBalancedAdjustments: FC<Props> = ({ customerId }) => {
  const [selectedView, setSelectedView] = useState(defaultView);
  const [selectedCurrency, setSelectedCurrency] = useState("All");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [showCreateCredit, setShowCreateCredit] = useState(false);
  const [transformedData, setTransformedData] = useState<CreditType[]>([]);
  const [sumOfCredits, setSumOfCredits] = useState(0);
  const queryClient = useQueryClient();

  useEffect(() => {
    let total = 0;
    transformedData.forEach((credit) => {
      if (credit.currency && credit.currency.code === selectedCurrency) {
        total += credit.amount;
      }
    });
    setSumOfCredits(total);
  }, [selectedCurrency, transformedData]);

  const { data, refetch }: UseQueryResult<CreditType[]> = useQuery<
    CreditType[]
  >(["balance_adjustments", customerId], () =>
    Credits.getCreditsByCustomer({
      customer_id: customerId,
    }).then((res) => res)
  );

  const deleteCredit = useMutation(
    (adjustment_id: string) =>
      Credits.deleteCredit(adjustment_id).then((v) => refetch()),
    {
      onSuccess: () => {
        toast.success("Successfully voided Credit", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to delete Credit", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const columns: ColumnsType<CreditType> = [
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      width: "20%",
      render: (amount: string, record) => (
        <span>
          {record.currency && record.currency.symbol}
          {parseFloat(amount).toFixed(2)}
        </span>
      ),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
    },
    {
      title: "Effective At",
      dataIndex: "effective_at",
      key: "effective_at",
      render: (effective_at: string) => (
        <span>{dayjs(effective_at).format("YYYY/MM/DD HH:mm")}</span>
      ),
    },
    {
      title: "Expires At",
      dataIndex: "expires_at",
      key: "expires_at",
      render: (expires_at: string) => (
        <div>
          {expires_at ? (
            <span>{dayjs(expires_at).format("YYYY/MM/DD HH:mm")}</span>
          ) : (
            "-"
          )}
        </div>
      ),
    },
  ];
  const navigate = useNavigate();

  // if (isLoading) {
  //   return (
  //     <div className="flex">
  //       <div className="m-auto">
  //         <LoadingSpinner />
  //       </div>
  //     </div>
  //   );
  // }

  const actionColumn = {
    title: "-",
    dataIndex: "actions",
    key: "actions",
    width: "1%",
    render: (_, record: CreditType) => (
      <Dropdown
        overlay={
          <Menu>
            <Menu.Item
              disabled={
                record.amount <= 0 ||
                record.status === "inactive" ||
                selectedView === views[1]
              }
              onClick={() => deleteCredit.mutate(record.credit_id)}
            >
              <div className="archiveLabel">Void Credit</div>
            </Menu.Item>
          </Menu>
        }
        trigger={["click"]}
      >
        <Button type="text" size="small" onClick={(e) => e.preventDefault()}>
          <MoreOutlined />
        </Button>
      </Dropdown>
    ),
  };

  useEffect(() => {
    if (data) {
      if (selectedView === views[0]) {
        const newData = data.map((credit) => ({
          ...credit,
          children: credit.drawdowns,
        }));
        setTransformedData(newData);
      } else {
        setTransformedData(data);
      }
    }
  }, [data, selectedView]);

  const getTableColumns = () => {
    if (selectedView === views[0]) {
      // for status, make ghreen if the status is active, red if it is inactive, and a dash if the amount on the credit is negative
      const statusColumn = {
        title: "Status",
        dataIndex: "status",
        key: "status",
        render: (status: string, record) => (
          <div>
            {record.amount <= 0 ? (
              "-"
            ) : status === "active" ? (
              <Tag color="green">Active</Tag>
            ) : (
              <Tag color="red">Inactive</Tag>
            )}
          </div>
        ),
      };
      return [...columns, statusColumn, actionColumn];
    }
    return [...columns, actionColumn];
  };

  return (
    <div>
      <h2 className="mb-2 pb-4 pt-4 font-bold text-main">Credits</h2>
      <div className="flex items-center justify-between pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center justify-between pr-6">
            <div className="mr-4">Currency:</div>
            <PricingUnitDropDown
              defaultValue="All"
              shouldShowAllOption
              setCurrentCurrency={setSelectedCurrency}
              setCurrentSymbol={setSelectedSymbol}
            />
          </div>
          <div className="flex items-center justify-between pr-6">
            <div className="mr-4">View:</div>
            <Select
              size="small"
              defaultValue={defaultView}
              onChange={setSelectedView}
              options={views.map((view) => ({ label: view, value: view }))}
            />
          </div>
        </div>
        <Button
          type="primary"
          className="hover:!bg-primary-700"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
          size="large"
          disabled={false}
          onClick={() => setShowCreateCredit(true)}
        >
          Create Credit
        </Button>
      </div>
      {showCreateCredit && (
        <CreateCredit
          customerId={customerId}
          onCancel={() => {
            setShowCreateCredit(false);
          }}
          onSubmit={() => {
            setShowCreateCredit(false);
            queryClient.invalidateQueries(["credits"]);
          }}
          visible={showCreateCredit}
        />
      )}
      {selectedCurrency !== "All" && (
        <div className="mb-2">
          Credit Balance: {selectedSymbol} {sumOfCredits}
        </div>
      )}
      {data?.length ? (
        <Table
          rowKey={(record) => record.credit_id}
          columns={getTableColumns()}
          dataSource={
            selectedCurrency === "All"
              ? transformedData
              : transformedData.filter(
                  (v) => v.currency.code === selectedCurrency
                )
          }
          pagination={{
            showTotal: (total, range) => (
              <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
            ),
            pageSize: 6,
          }}
        />
      ) : (
        <div className="flex flex-col items-center p-4 justify-center bg-card">
          <div className="text-lg mt-2 mb-2 font-alliance">
            No credits have been created for this customer.
          </div>
          <div className="text-base Inter mt-2 mb-2">
            Credits are used to adjust a customer's balance.
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerBalancedAdjustments;
