import {Table, Button, Select, Dropdown, Menu, Tag} from "antd";
import { FC, useState } from "react";
// @ts-ignore
import React from "react";
import { BalanceAdjustments } from "../../types/invoice-type";
// @ts-ignore
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import PricingUnitDropDown from "../PricingUnitDropDown";
import {useMutation, useQuery, useQueryClient, UseQueryResult} from "react-query";
import { BalanceAdjustment, Plan } from "../../api/api";
import LoadingSpinner from "../LoadingSpinner";
import { MoreOutlined } from "@ant-design/icons";
import { InitialExternalLinks } from "../../types/plan-type";
import { toast } from "react-toastify";
import {ColumnsType} from "antd/es/table";
import {TableRowSelection} from "antd/es/table/interface";

interface Props {
  customerId: string;
}

interface DataType extends BalanceAdjustments{
  children?: DataType[];
}

const views = ["grouped", "chronological"];
const defaultView = "grouped"

const CustomerBalancedAdjustments: FC<Props> = ({ customerId }) => {
  const [selectedView, setSelectedView] = useState(defaultView);
  const [selectedCurrency, setSelectedCurrency] = useState("All");

  const { data, isLoading, refetch }: UseQueryResult<BalanceAdjustments[]> = useQuery<
    BalanceAdjustments[]
  >(["balance_adjustments", selectedView], () =>
    BalanceAdjustment.getCreditsByCustomer({
      customer_id: customerId,
    }).then((res) => {
      return res;
    })
  );

  const deleteCredit = useMutation(
    (adjustment_id: string) => {
        return BalanceAdjustment.deleteCredit(adjustment_id).then(v => refetch())
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

  const columns : ColumnsType<DataType>  = [
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      render: (amount: string, record) => <span>{record.pricing_unit.symbol}{parseFloat(amount).toFixed(2)}</span>,
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      width: '20%',
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

  if (isLoading) {
    return (
      <div className="flex">
        <div className="m-auto">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  const actionColumn = {
      title: "-",
      dataIndex: "actions",
      key: "actions",
      width: '1%',
      render: (_, record: BalanceAdjustments) => (
        <Dropdown
          overlay={
            <Menu>
              <Menu.Item
                disabled={record.amount <= 0 || record.status === "inactive" || selectedView === views[1]}
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

  const getTableData = () => {
        if (selectedView === views[0]) {
            const parentAdjustments = data?.filter(item => !item.parent_adjustment_id)
            return parentAdjustments.map(parentAdjustment => {
                const childAdjustments = data?.filter(item => item.parent_adjustment_id === parentAdjustment.adjustment_id)
                if (childAdjustments.length) {
                    return {
                        ...parentAdjustment,
                        children: data?.filter(item => item.parent_adjustment_id === parentAdjustment.adjustment_id)
                    }
                } else {
                    return {
                        ...parentAdjustment,
                    }
                }
            })
        }
        return data
    }

  const getTableColumns = () => {
        if (selectedView === views[0]) {
            const status = {
                    title: "Status",
                    dataIndex: "status",
                    key: "status",
                    render: (status: string) => <Tag color={status === "active" ? "green" : "red"}>{status}</Tag>,
                };
            return [
                ...columns,
                status,
                actionColumn
            ]
        }
        return [
            ...columns,
            actionColumn
        ]
    }

  return (
    <div>
      <div className="flex items-center justify-between pb-5">
        <Button
          type="primary"
          className="mr-4"
          size="large"
          onClick={() => navigate("/customers-create-credit/" + customerId)}
        >
          Create Credit
        </Button>
        <div className="flex items-center justify-between">
          <div className="flex items-center justify-between pr-6">
            <div className="mr-4">Currency:</div>
            <PricingUnitDropDown
              defaultValue="All"
              shouldShowAllOption
              setCurrentCurrency={setSelectedCurrency}
            />
          </div>
          <div className="flex items-center justify-between pr-6">
            <div className="mr-4">View:</div>
            <Select
              size="small"
              defaultValue={defaultView}
              onChange={setSelectedView}
              options={views.map((view) => {
                return { label: view, value: view};
              })}
            />
          </div>
        </div>
      </div>
      {!!data?.length ? (
        <Table
          rowKey={(record) => record.adjustment_id}
          columns={getTableColumns()}
          dataSource={selectedCurrency === "All" ? getTableData() :getTableData().filter(v => v.pricing_unit.code === selectedCurrency)}
          pagination={{ pageSize: 10 }}
        />
      ) : (
        <p>No Credit Items Found</p>
      )}
    </div>
  );
};

export default CustomerBalancedAdjustments;
