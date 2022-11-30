import { Table, Button, Select, Dropdown, Menu } from "antd";
import { FC, useState } from "react";
// @ts-ignore
import React from "react";
import { BalanceAdjustments } from "../../types/invoice-type";
// @ts-ignore
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import PricingUnitDropDown from "../PricingUnitDropDown";
import { useMutation, useQuery, UseQueryResult } from "react-query";
import { BalanceAdjustment, Plan } from "../../api/api";
import LoadingSpinner from "../LoadingSpinner";
import { MoreOutlined } from "@ant-design/icons";
import { InitialExternalLinks } from "../../types/plan-type";
import { toast } from "react-toastify";

interface Props {
  customerId: string;
}

const views = ["grouped", "chronological"];

const CustomerBalancedAdjustments: FC<Props> = ({ customerId }) => {
  const [selectedView, setSelectedView] = useState(views[0]);

  const { data, isLoading }: UseQueryResult<BalanceAdjustments[]> = useQuery<
    BalanceAdjustments[]
  >(["balanceAdjustments", selectedView], () =>
    BalanceAdjustment.getCreditsByCustomer({
      customer_id: customerId,
      format: selectedView.toLowerCase(),
    }).then((res) => {
      return res;
    })
  );

  const deleteCredit = useMutation(
    (adjustment_id: string) => BalanceAdjustment.deleteCredit(adjustment_id),
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

  const columns = [
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      render: (amount: string) => <span>${parseFloat(amount).toFixed(2)}</span>,
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
    {
      title: "Actions",
      dataIndex: "actions",
      key: "actions",
      render: (_, record: BalanceAdjustments) => (
        <Dropdown
          overlay={
            <Menu>
              <Menu.Item
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
    },
  ];
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div className="flex h-screen">
        <div className="m-auto">
          <LoadingSpinner />
        </div>
      </div>
    );
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
              defaultValue={"USD"}
              setCurrentCurrency={(value) => console.log(value)}
            />
          </div>
          <div className="flex items-center justify-between pr-6">
            <div className="mr-4">View:</div>
            <Select
              size="small"
              defaultValue={views[0]}
              onChange={(value) => setSelectedView(value)}
              options={views.map((view) => {
                return { label: view, value: view, disabled: view == views[0] };
              })}
            />
          </div>
        </div>
      </div>
      {!!data?.length ? (
        <Table
          columns={columns}
          dataSource={data}
          pagination={{ pageSize: 10 }}
        />
      ) : (
        <p>No Credit Items Found</p>
      )}
    </div>
  );
};

export default CustomerBalancedAdjustments;
