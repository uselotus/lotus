import { Table, Button, Select, Dropdown, Menu, Tag } from "antd";
import { FC, useState, useEffect } from "react";
// @ts-ignore
import React from "react";
import { BalanceAdjustmentType } from "../../types/balance-adjustment";
// @ts-ignore
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import PricingUnitDropDown from "../PricingUnitDropDown";
import { useMutation, useQuery, UseQueryResult } from "react-query";
import { BalanceAdjustment } from "../../api/api";
import { MoreOutlined } from "@ant-design/icons";
import { toast } from "react-toastify";
import { ColumnsType } from "antd/es/table";
import CreateCredit from "../../pages/CreateBalanceAdjustment";

interface Props {
  customerId: string;
}

interface DataType extends BalanceAdjustmentType {
  children?: DataType[];
}

const views = ["grouped", "chronological"];
const defaultView = "grouped";

const CustomerBalancedAdjustments: FC<Props> = ({ customerId }) => {
  const [selectedView, setSelectedView] = useState(defaultView);
  const [selectedCurrency, setSelectedCurrency] = useState("All");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [showCreateCredit, setShowCreateCredit] = useState(false);
  const [transformedData, setTransformedData] = useState<DataType[]>([]);
  const [sumOfCredits, setSumOfCredits] = useState(0);

  useEffect(() => {
    let total: number = 0;
    transformedData.forEach((credit) => {
      if (credit.pricing_unit.code === selectedCurrency) {
        total += credit.amount;
      }
    });
    setSumOfCredits(total);
  }, [selectedCurrency, transformedData]);

  const { data, isLoading, refetch }: UseQueryResult<BalanceAdjustmentType[]> =
    useQuery<BalanceAdjustmentType[]>(["balance_adjustments", customerId], () =>
      BalanceAdjustment.getCreditsByCustomer({
        customer_id: customerId,
      }).then((res) => {
        return res;
      })
    );

  const deleteCredit = useMutation(
    (adjustment_id: string) => {
      return BalanceAdjustment.deleteCredit(adjustment_id).then((v) =>
        refetch()
      );
    },
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

  const columns: ColumnsType<DataType> = [
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      width: "20%",
      render: (amount: string, record) => (
        <span>
          {record.pricing_unit.symbol}
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
    render: (_, record: BalanceAdjustmentType) => (
      <Dropdown
        overlay={
          <Menu>
            <Menu.Item
              disabled={
                record.amount <= 0 ||
                record.status === "inactive" ||
                selectedView === views[1]
              }
              onClick={() => deleteCredit.mutate(record.adjustment_id)}
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
        const parentAdjustments = data.filter(
          (item) => !item.parent_adjustment_id
        );
        const newData = parentAdjustments.map((parentAdjustment) => {
          const childAdjustments = data?.filter(
            (item) =>
              item.parent_adjustment_id === parentAdjustment.adjustment_id
          );
          if (childAdjustments.length) {
            return {
              ...parentAdjustment,
              children: data?.filter(
                (item) =>
                  item.parent_adjustment_id === parentAdjustment.adjustment_id
              ),
            };
          } else {
            return {
              ...parentAdjustment,
            };
          }
        });
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
              options={views.map((view) => {
                return { label: view, value: view };
              })}
            />
          </div>
        </div>
        {!showCreateCredit ? (
          <Button
            type="primary"
            className="mr-4"
            size="large"
            disabled={false}
            onClick={() => setShowCreateCredit(true)}
          >
            Create Credit
          </Button>
        ) : (
          <Button
            type="default"
            className="mr-4"
            size="large"
            disabled={false}
            onClick={() => setShowCreateCredit(false)}
          >
            Close Create Credit
          </Button>
        )}
      </div>
      {showCreateCredit && (
        <CreateCredit
          customerId={customerId}
          onSubmit={() => {
            setShowCreateCredit(false);
          }}
        />
      )}
      {selectedCurrency !== "All" && (
        <div className="mb-2">
          Credit Balance: {selectedSymbol} {sumOfCredits}
        </div>
      )}
      {!!data?.length ? (
        <Table
          rowKey={(record) => record.adjustment_id}
          columns={getTableColumns()}
          dataSource={
            selectedCurrency === "All"
              ? transformedData
              : transformedData.filter(
                  (v) => v.pricing_unit.code === selectedCurrency
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
        <p>No Credit Items Found</p>
      )}
    </div>
  );
};

export default CustomerBalancedAdjustments;
