import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/Customers/CustomerTable";
import {
  CustomerPlus,
  CustomerTotal,
  CustomerType,
} from "../types/customer-type";
import { Customer } from "../api/api";

import { Button } from "antd";
import LoadingSpinner from "../components/LoadingSpinner";
import {
  useQuery,
  UseQueryResult,
  useQueryClient,
  useMutation,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import CreateCustomerForm, {
  CreateCustomerState,
} from "../components/Customers/CreateCustomerForm";
import { toast } from "react-toastify";
import {LotusFilledButton} from "../components/base/Button";

const ViewCustomers: FC = () => {
  const queryClient = useQueryClient();
  const [visible, setVisible] = useState(false);

  const { data, isLoading }: UseQueryResult<CustomerPlus[]> = useQuery<
    CustomerPlus[]
  >(["customer_list"], () =>
    Customer.getCustomers().then((res) => {
      return res;
    })
  );
  const { data: customerTotals, isLoading: totalLoading } = useQuery<
    CustomerTotal[]
  >(["customer_totals"], () =>
    Customer.getCustomerTotals().then((res) => {
      return res;
    })
  );

  const mutation = useMutation(
    (post: CustomerType) => Customer.createCustomer(post),
    {
      onSuccess: () => {
        setVisible(false);
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_totals"]);
        toast.success("Customer created successfully", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Error creating customer", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const openCustomerModal = () => {
    setVisible(true);
  };

  const onCancel = () => {
    setVisible(false);
  };

  const onSave = (state: CreateCustomerState) => {
    const customerInstance: CustomerType = {
      customer_id: state.customer_id,
      customer_name: state.name,
      email: state.email,
      payment_provider: state.payment_provider,
      payment_provider_id: state.payment_provider_id,
    };
    mutation.mutate(customerInstance);
    onCancel();
  };

  return (
    <PageLayout
      title="Customers"
      extra={[
        <LotusFilledButton text="Create Customer" onClick={openCustomerModal}/>,
      ]}
    >
      <div>
        {isLoading || data === undefined ? (
          <LoadingSpinner />
        ) : (
          <CustomerTable customerArray={data} totals={customerTotals} />
        )}
        <CreateCustomerForm
          visible={visible}
          onSave={onSave}
          onCancel={onCancel}
        />
      </div>
    </PageLayout>
  );
};

export default ViewCustomers;
